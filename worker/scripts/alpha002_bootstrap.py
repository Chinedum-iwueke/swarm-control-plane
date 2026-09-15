#!/usr/bin/env python3
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
DEFAULT_PACKAGE = "vm1-alpha-research-executor"
WORKLOAD_SCOPES = [
    "control:read",
    "heartbeat:write",
    "identity:read",
    "package:read",
    "task:execute",
    "task:lease",
]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def call(client: httpx.Client, method: str, path: str, payload: dict | None = None):
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.chmod(mode)
    temporary.replace(path)


def ensure_workload_identity(
    api: httpx.Client,
    state: dict,
    *,
    expires_at: str,
) -> dict:
    identities = call(api, "GET", "/v1/workload-identities")
    matches = [
        item
        for item in identities
        if item["agent_id"] == state["agent_id"]
        and item["charter_id"] == state["charter_id"]
        and item["package_id"] == state["package_id"]
        and item["status"] == "active"
    ]
    if len(matches) > 1:
        raise RuntimeError("Multiple active workload identities match the executor.")
    expected_id = state.get("workload_identity_id")
    if expected_id and (not matches or matches[0]["id"] != expected_id):
        raise RuntimeError("Persisted executor workload identity is no longer active.")
    if matches:
        identity = matches[0]
    else:
        identity = call(
            api,
            "POST",
            "/v1/workload-identities",
            {
                "agent_id": state["agent_id"],
                "charter_id": state["charter_id"],
                "package_id": state["package_id"],
                "version": "1.0.0",
                "audience": "invariance-control-plane",
                "scopes": WORKLOAD_SCOPES,
                "accountable_owner": "senior-quantitative-research",
                "expires_at": expires_at,
                "created_by": "founder-operator",
            },
        )
    if sorted(identity["scopes"]) != WORKLOAD_SCOPES:
        raise RuntimeError("Executor workload identity has unexpected scopes.")
    call(
        api,
        "POST",
        f"/v1/workload-identities/{identity['id']}/bind-credentials",
        {"actor": "founder-operator"},
    )
    return identity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--recover-registration", action="store_true")
    args = parser.parse_args()
    package_name = args.package
    if args.state.exists() != args.environment.exists():
        raise RuntimeError(
            "Executor state is partial; refusing implicit credential recovery."
        )
    if len(args.source_commit) != 40:
        raise RuntimeError("A full control-plane source commit is required.")
    signing_secret = os.environ["SWARM_PACKAGE_SIGNING_SECRET"]
    manifest = load_role_package(
        ROOT / "role-packages" / package_name / "manifest.yaml", ROOT / "workflows"
    ).manifest
    canonical = canonical_manifest(manifest)
    manifest_digest = hashlib.sha256(canonical).hexdigest()
    if args.state.exists():
        state = json.loads(args.state.read_text(encoding="utf-8"))
        if (
            state.get("slug") != package_name
            or state.get("manifest_digest") != manifest_digest
            or state.get("source_commit") != args.source_commit
        ):
            raise RuntimeError(
                "Existing executor state differs; use an explicit package/credential rotation."
            )
        if args.state.stat().st_mode & 0o077 or args.environment.stat().st_mode & 0o077:
            raise RuntimeError("Existing executor state files are not mode 0600.")
        with httpx.Client(
            base_url=os.environ["SWARM_API_URL"].rstrip("/"),
            headers={
                "Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
            },
            timeout=60,
        ) as api:
            identity = ensure_workload_identity(
                api,
                state,
                expires_at=(datetime.now(UTC) + timedelta(days=365)).isoformat(),
            )
        state["workload_identity_id"] = identity["id"]
        state["workload_scopes"] = WORKLOAD_SCOPES
        atomic_write(args.state, json.dumps(state, indent=2, sort_keys=True) + "\n")
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=60,
    ) as api:
        packages = call(api, "GET", "/v1/packages")
        package = next(
            (
                item
                for item in packages
                if item["name"] == package_name and item["version"] == manifest.version
            ),
            None,
        )
        if package is None:
            package = call(
                api,
                "POST",
                "/v1/packages",
                {
                    "manifest": manifest.model_dump(mode="json"),
                    "manifest_digest": manifest_digest,
                    "signature": hmac.new(
                        signing_secret.encode(), canonical, hashlib.sha256
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        if package["manifest_digest"] != manifest_digest:
            raise RuntimeError("Existing package content differs from local source.")
        agents = call(api, "GET", "/v1/agents")
        existing_agent = next(
            (item for item in agents if item["slug"] == package_name), None
        )
        if existing_agent and not args.recover_registration:
            raise RuntimeError("Executor identity exists; refusing implicit rotation.")
        if existing_agent:
            if (
                existing_agent["machine"] != "vm1-developer"
                or existing_agent["role"] != manifest.role
                or sorted(existing_agent["capabilities"])
                != sorted(manifest.required_capabilities)
                or existing_agent["risk_ceiling"] != 0
                or not existing_agent["is_enabled"]
            ):
                raise RuntimeError(
                    "Partial executor registration differs from the reviewed package."
                )
            registration = {"agent": existing_agent}
        else:
            registration = call(
                api,
                "POST",
                "/v1/agents",
                {
                    "slug": package_name,
                    "display_name": "VM1 Alpha Research Executor",
                    "role": manifest.role,
                    "machine": "vm1-developer",
                    "hermes_profile": package_name,
                    "capabilities": manifest.required_capabilities,
                    "risk_ceiling": 0,
                },
            )
        deployments = call(api, "GET", "/v1/packages/deployments")
        active_deployments = [
            item["deployment"]
            for item in deployments
            if item["deployment"]["agent_id"] == registration["agent"]["id"]
            and item["deployment"]["is_active"]
        ]
        if active_deployments and (
            len(active_deployments) != 1
            or active_deployments[0]["package_id"] != package["id"]
        ):
            raise RuntimeError(
                "Partial executor deployment differs from the reviewed package."
            )
        deployment = (
            active_deployments[0]
            if active_deployments
            else call(
                api,
                "POST",
                "/v1/packages/deployments",
                {
                    "agent_id": registration["agent"]["id"],
                    "package_id": package["id"],
                    "deployed_by": "founder-operator",
                },
            )
        )
        charter_manifest = {
            "schema_version": "agent-charter-v1.0.0",
            "role": manifest.role,
            "responsibilities": [
                f"Execute one leased no-capital question through Bulletproof only as {package_name}."
            ],
            "capabilities": manifest.required_capabilities,
            "allowed_machines": ["vm1-developer"],
            "allowed_task_types": manifest.task_types,
            "allowed_repositories": ["bulletproof_bt"],
            "risk_ceiling": 0,
            "accountable_owner": "senior-quantitative-research",
            "conflicts": [],
            "forbidden_actions": [
                "capital-allocation",
                "order-placement",
                "live-trading",
                "production-promotion",
                "self-approval",
            ],
        }
        charters = call(api, "GET", "/v1/agent-governance/charters")
        matches = [
            item
            for item in charters
            if item["agent_id"] == registration["agent"]["id"]
            and item["version"] == "1.0.0"
        ]
        if matches and (
            len(matches) != 1
            or matches[0]["manifest_digest"] != digest(charter_manifest)
        ):
            raise RuntimeError(
                "Partial executor charter differs from the reviewed package."
            )
        charter = (
            matches[0]
            if matches
            else call(
                api,
                "POST",
                "/v1/agent-governance/charters",
                {
                    "agent_id": registration["agent"]["id"],
                    "version": "1.0.0",
                    "manifest": charter_manifest,
                    "manifest_digest": digest(charter_manifest),
                    "created_by": "founder-operator",
                },
            )
        )
        charter = call(
            api,
            "POST",
            f"/v1/agent-governance/charters/{charter['id']}/activate",
            {"activated_by": "founder-operator"},
        )
        grant_ids = []
        for capability in manifest.required_capabilities:
            grant = call(
                api,
                "POST",
                "/v1/agent-governance/grants",
                {
                    "agent_id": registration["agent"]["id"],
                    "charter_id": charter["id"],
                    "package_id": package["id"],
                    "capability": capability,
                    "machine": "vm1-developer",
                    "task_types": manifest.task_types,
                    "repositories": ["bulletproof_bt"],
                    "risk_ceiling": 0,
                    "accountable_owner": "senior-quantitative-research",
                    "granted_by": "founder-operator",
                    "reason": "ALPHA-002 continuous no-capital scientific execution",
                    "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                },
            )
            grant_ids.append(grant["id"])
        state = {
            "agent_id": registration["agent"]["id"],
            "slug": package_name,
            "package_id": package["id"],
            "deployment_id": deployment["id"],
            "charter_id": charter["id"],
            "grant_ids": grant_ids,
            "manifest_digest": manifest_digest,
            "source_commit": args.source_commit,
        }
        identity = ensure_workload_identity(
            api,
            state,
            expires_at=(datetime.now(UTC) + timedelta(days=365)).isoformat(),
        )
        state["workload_identity_id"] = identity["id"]
        state["workload_scopes"] = WORKLOAD_SCOPES
        if existing_agent:
            rotated = call(
                api,
                "POST",
                f"/v1/workload-identities/{identity['id']}/credentials/rotate",
                {"actor": "founder-operator", "overlap_seconds": 30},
            )
            registration["credential"] = {"token": rotated["token"]}
    atomic_write(args.state, json.dumps(state, indent=2, sort_keys=True) + "\n")
    environment = "\n".join(
        [
            f"SWARM_API_URL={os.environ['SWARM_API_URL']}",
            f"SWARM_AGENT_TOKEN={registration['credential']['token']}",
            f"SWARM_AGENT_SLUG={package_name}",
            "SWARM_MACHINE=vm1-developer",
            "SWARM_POLL_INTERVAL_SECONDS=10",
            "SWARM_TASK_HEARTBEAT_SECONDS=30",
            "SWARM_LEASE_SECONDS=1800",
            "SWARM_REPOSITORY_ROOT=/home/omenka/Projects",
            "SWARM_WORKSPACE_ROOT=/home/omenka/Projects/swarm-agent-workspaces",
            "SWARM_WORKFLOW_DIRECTORY=/home/omenka/Projects/swarm-control-plane/worker/workflows",
            f"SWARM_ROLE_PACKAGE_MANIFEST=/home/omenka/Projects/swarm-control-plane/worker/role-packages/{package_name}/manifest.yaml",
            "",
        ]
    )
    atomic_write(args.environment, environment)
    if existing_agent:
        with httpx.Client(
            base_url=os.environ["SWARM_API_URL"].rstrip("/"),
            headers={
                "Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
            },
            timeout=60,
        ) as api:
            call(
                api,
                "POST",
                f"/v1/workload-identities/{identity['id']}/credentials/finalize",
                {"actor": "founder-operator"},
            )
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
