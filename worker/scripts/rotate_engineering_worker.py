#!/usr/bin/env python3
"""Rotate the generic VM1 engineering worker onto its current signed package."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from swarm_worker.role_package import canonical_manifest, load_role_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "vm1-engineering-worker"
AGENT_SLUG = "vm1-developer-coder"
SCOPES = [
    "control:read",
    "heartbeat:write",
    "identity:read",
    "package:read",
    "task:execute",
    "task:lease",
]


def request(
    client: httpx.Client,
    method: str,
    path: str,
    payload: dict | None = None,
):
    response = client.request(method, path, json=payload)
    if response.is_error:
        raise RuntimeError(
            f"{method} {path} failed ({response.status_code}): {response.text}"
        )
    return response.json()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.chmod(0o600)
    temporary.replace(path)


def replace_environment_token(path: Path, token: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    replacement = f"SWARM_AGENT_TOKEN={token}"
    output = []
    replaced = False
    for line in lines:
        if line.startswith("SWARM_AGENT_TOKEN="):
            output.append(replacement)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        raise RuntimeError("Worker environment has no SWARM_AGENT_TOKEN entry.")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if len(args.source_commit) != 40:
        raise RuntimeError("A full control-plane source commit is required.")
    if not args.environment.exists():
        raise RuntimeError("Worker environment does not exist.")
    if args.environment.stat().st_mode & 0o077:
        raise RuntimeError("Worker environment must be mode 0600.")

    package = load_role_package(
        ROOT / "role-packages" / PACKAGE_NAME / "manifest.yaml",
        ROOT / "workflows",
    ).manifest
    canonical = canonical_manifest(package)
    manifest_digest = hashlib.sha256(canonical).hexdigest()
    headers = {
        "Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
    }
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers=headers,
        timeout=60,
    ) as api:
        packages = request(api, "GET", "/v1/packages")
        registered = next(
            (
                item
                for item in packages
                if item["name"] == PACKAGE_NAME
                and item["version"] == package.version
            ),
            None,
        )
        if registered is None:
            registered = request(
                api,
                "POST",
                "/v1/packages",
                {
                    "manifest": package.model_dump(mode="json"),
                    "manifest_digest": manifest_digest,
                    "signature": hmac.new(
                        os.environ["SWARM_PACKAGE_SIGNING_SECRET"].encode(),
                        canonical,
                        hashlib.sha256,
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        if registered["manifest_digest"] != manifest_digest:
            raise RuntimeError("Registered package content differs from local source.")

        agents = request(api, "GET", "/v1/agents")
        agent = next(item for item in agents if item["slug"] == AGENT_SLUG)
        deployments = request(api, "GET", "/v1/packages/deployments")
        active_deployments = [
            row["deployment"]
            for row in deployments
            if row["deployment"]["agent_id"] == agent["id"]
            and row["deployment"]["is_active"]
        ]
        deployment = next(
            (
                item
                for item in active_deployments
                if item["package_id"] == registered["id"]
            ),
            None,
        )
        if deployment is None:
            deployment = request(
                api,
                "POST",
                "/v1/packages/deployments",
                {
                    "agent_id": agent["id"],
                    "package_id": registered["id"],
                    "deployed_by": "founder-operator",
                },
            )

        charters = request(api, "GET", "/v1/agent-governance/charters")
        charter = next(
            item
            for item in charters
            if item["agent_id"] == agent["id"] and item["status"] == "active"
        )
        grants = request(api, "GET", "/v1/agent-governance/grants")
        grant_ids = []
        for capability in package.required_capabilities:
            grant = next(
                (
                    item
                    for item in grants
                    if item["agent_id"] == agent["id"]
                    and item["package_id"] == registered["id"]
                    and item["capability"] == capability
                    and item["status"] == "active"
                ),
                None,
            )
            if grant is None:
                grant = request(
                    api,
                    "POST",
                    "/v1/agent-governance/grants",
                    {
                        "agent_id": agent["id"],
                        "charter_id": charter["id"],
                        "package_id": registered["id"],
                        "capability": capability,
                        "machine": agent["machine"],
                        "task_types": package.task_types,
                        "repositories": package.repository_profile.repositories,
                        "risk_ceiling": package.risk_ceiling,
                        "accountable_owner": charter["manifest"][
                            "accountable_owner"
                        ],
                        "granted_by": "founder-operator",
                        "reason": (
                            "Signed generic engineering package rotation "
                            f"{manifest_digest}"
                        ),
                        "expires_at": (
                            datetime.now(UTC) + timedelta(days=365)
                        ).isoformat(),
                    },
                )
            grant_ids.append(grant["id"])

        identities = request(api, "GET", "/v1/workload-identities")
        identity = next(
            (
                item
                for item in identities
                if item["agent_id"] == agent["id"]
                and item["package_id"] == registered["id"]
                and item["status"] == "active"
            ),
            None,
        )
        if identity is None:
            identity = request(
                api,
                "POST",
                "/v1/workload-identities",
                {
                    "agent_id": agent["id"],
                    "charter_id": charter["id"],
                    "package_id": registered["id"],
                    "version": package.version,
                    "audience": "invariance-control-plane",
                    "scopes": SCOPES,
                    "accountable_owner": charter["manifest"]["accountable_owner"],
                    "expires_at": (
                        datetime.now(UTC) + timedelta(days=365)
                    ).isoformat(),
                    "created_by": "founder-operator",
                },
            )
        request(
            api,
            "POST",
            f"/v1/workload-identities/{identity['id']}/bind-credentials",
            {"actor": "founder-operator"},
        )
        rotation = request(
            api,
            "POST",
            f"/v1/workload-identities/{identity['id']}/credentials/rotate",
            {"actor": "founder-operator", "overlap_seconds": 120},
        )
        atomic_write(
            args.environment,
            replace_environment_token(args.environment, rotation["token"]),
        )
        request(
            api,
            "POST",
            f"/v1/workload-identities/{identity['id']}/credentials/finalize",
            {"actor": "founder-operator"},
        )
        for prior in active_deployments:
            if prior["id"] != deployment["id"]:
                request(
                    api,
                    "POST",
                    f"/v1/packages/deployments/{prior['id']}/revoke",
                )
        for grant in grants:
            if (
                grant["agent_id"] == agent["id"]
                and grant["status"] == "active"
                and grant["package_id"] != registered["id"]
            ):
                request(
                    api,
                    "POST",
                    f"/v1/agent-governance/grants/{grant['id']}/revoke",
                    {
                        "revoked_by": "founder-operator",
                        "reason": f"Superseded by {PACKAGE_NAME} {package.version}.",
                    },
                )

    state = {
        "agent_id": agent["id"],
        "charter_id": charter["id"],
        "deployment_id": deployment["id"],
        "grant_ids": grant_ids,
        "manifest_digest": manifest_digest,
        "package_id": registered["id"],
        "slug": AGENT_SLUG,
        "source_commit": args.source_commit,
        "workload_identity_id": identity["id"],
        "workload_scopes": SCOPES,
    }
    atomic_write(args.state, json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
