from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from swarm_worker.role_package import canonical_manifest, load_role_package

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "exec1": {
        "package": "exec1-fleet-observer",
        "slug": "exec1-fleet-observer",
        "display_name": "EXEC1 Fleet Observer",
        "machine": "exec1-execution",
    },
    "vm1": {
        "package": "vm1-fleet-observer",
        "slug": "vm1-fleet-observer",
        "display_name": "VM1 Fleet Observer",
        "machine": "vm1-developer",
    },
    "vm2": {
        "package": "vm2-fleet-observer",
        "slug": "vm2-fleet-observer",
        "display_name": "VM2 Fleet Observer",
        "machine": "vm2-deployment",
    },
}


def request(client: httpx.Client, method: str, path: str, payload: dict | None = None):
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def digest_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def workload_scopes(manifest: dict) -> list[str]:
    scopes = {"control:read", "heartbeat:write", "identity:read", "package:read"}
    task_types = set(manifest.get("task_types", []))
    if task_types:
        scopes |= {"task:execute", "task:lease"}
    if "fleet_observation" in task_types:
        scopes.add("fleet:write")
    return sorted(scopes)


def ensure_governance(
    api: httpx.Client, *, agent: dict, package: dict
) -> dict[str, object]:
    manifest = package["manifest"]
    charter_manifest = {
        "schema_version": "agent-charter-v1.0.0",
        "role": manifest["role"],
        "responsibilities": [
            "Publish bounded fleet health observations from the assigned machine."
        ],
        "capabilities": manifest["required_capabilities"],
        "allowed_machines": [agent["machine"]],
        "allowed_task_types": manifest["task_types"],
        "allowed_repositories": manifest["repository_profile"]["repositories"],
        "risk_ceiling": min(agent["risk_ceiling"], manifest["risk_ceiling"]),
        "accountable_owner": "company-operations",
        "conflicts": [],
        "forbidden_actions": [
            "capital-allocation",
            "order-placement",
            "live-trading",
        ],
    }
    charter_digest = digest_json(charter_manifest)
    charters = request(api, "GET", "/v1/agent-governance/charters")
    charter = next(
        (
            item
            for item in charters
            if item["agent_id"] == agent["id"]
            and item["manifest_digest"] == charter_digest
        ),
        None,
    )
    if charter is None:
        charter = request(
            api,
            "POST",
            "/v1/agent-governance/charters",
            {
                "agent_id": agent["id"],
                "version": f"1.0.{sum(item['agent_id'] == agent['id'] for item in charters)}",
                "manifest": charter_manifest,
                "manifest_digest": charter_digest,
                "created_by": "founder-operator",
            },
        )
    if charter["status"] != "active":
        charter = request(
            api,
            "POST",
            f"/v1/agent-governance/charters/{charter['id']}/activate",
            {"activated_by": "founder-operator"},
        )

    now = datetime.now(UTC)
    grants = request(api, "GET", "/v1/agent-governance/grants")
    grant_ids: list[str] = []
    for capability in manifest["required_capabilities"]:
        grant = next(
            (
                item
                for item in grants
                if item["agent_id"] == agent["id"]
                and item["charter_id"] == charter["id"]
                and item["package_id"] == package["id"]
                and item["capability"] == capability
                and item["status"] == "active"
                and datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00"))
                > now
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
                    "package_id": package["id"],
                    "capability": capability,
                    "machine": agent["machine"],
                    "task_types": manifest["task_types"],
                    "repositories": manifest["repository_profile"]["repositories"],
                    "risk_ceiling": charter_manifest["risk_ceiling"],
                    "accountable_owner": "company-operations",
                    "granted_by": "founder-operator",
                    "reason": f"OPS-004 active package {package['manifest_digest']}",
                    "expires_at": (now + timedelta(days=365)).isoformat(),
                },
            )
            grants.append(grant)
        grant_ids.append(grant["id"])

    identities = request(api, "GET", "/v1/workload-identities")
    identity = next(
        (
            item
            for item in identities
            if item["agent_id"] == agent["id"]
            and item["charter_id"] == charter["id"]
            and item["package_id"] == package["id"]
            and item["status"] == "active"
            and datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00")) > now
        ),
        None,
    )
    scopes = workload_scopes(manifest)
    if identity is None:
        identity = request(
            api,
            "POST",
            "/v1/workload-identities",
            {
                "agent_id": agent["id"],
                "charter_id": charter["id"],
                "package_id": package["id"],
                "version": f"1.0.{sum(item['agent_id'] == agent['id'] for item in identities)}",
                "audience": "invariance-control-plane",
                "scopes": scopes,
                "accountable_owner": "company-operations",
                "expires_at": (now + timedelta(days=90)).isoformat(),
                "created_by": "founder-operator",
            },
        )
    elif identity["scopes"] != scopes:
        raise RuntimeError(
            "Existing workload identity scopes differ from package authority."
        )
    request(
        api,
        "POST",
        f"/v1/workload-identities/{identity['id']}/bind-credentials",
        {"actor": "founder-operator"},
    )
    return {
        "charter_id": charter["id"],
        "grant_ids": grant_ids,
        "workload_identity_id": identity["id"],
        "workload_scopes": scopes,
    }


def repair_governance(api: httpx.Client, state: dict) -> dict[str, object]:
    agents = request(api, "GET", "/v1/agents")
    agent = next((item for item in agents if item["id"] == state["agent_id"]), None)
    packages = request(api, "GET", "/v1/packages")
    package = next(
        (item for item in packages if item["id"] == state["package_id"]), None
    )
    deployments = request(api, "GET", "/v1/packages/deployments")
    deployment = next(
        (
            item["deployment"]
            for item in deployments
            if item["deployment"]["id"] == state["deployment_id"]
        ),
        None,
    )
    if (
        agent is None
        or package is None
        or deployment is None
        or agent["slug"] != state["slug"]
        or agent["machine"] != state["machine"]
        or package["manifest_digest"] != state["manifest_digest"]
        or deployment["agent_id"] != agent["id"]
        or deployment["package_id"] != package["id"]
        or not deployment["is_active"]
    ):
        raise RuntimeError(
            "Recorded observer state does not match active control-plane objects."
        )
    return ensure_governance(api, agent=agent, package=package)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap one OPS-004 fleet observer")
    parser.add_argument("profile", choices=sorted(PROFILES))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--repair-governance", action="store_true")
    args = parser.parse_args()
    if args.repair_governance and not args.state.exists():
        raise RuntimeError("Repair requires an existing observer state file.")
    if not args.repair_governance and args.state.exists():
        raise RuntimeError(
            "State already exists; refusing implicit credential rotation."
        )
    if not args.repair_governance and (
        args.source_commit is None or len(args.source_commit) != 40
    ):
        raise RuntimeError("A full source commit is required.")
    signing_secret = os.environ.get("SWARM_PACKAGE_SIGNING_SECRET")
    if not args.repair_governance and (
        signing_secret is None or len(signing_secret) < 32
    ):
        raise RuntimeError("Protected package signing secret is unavailable.")
    profile = PROFILES[args.profile]
    package_name = profile["package"]
    manifest = load_role_package(
        ROOT / "role-packages" / package_name / "manifest.yaml", ROOT / "workflows"
    ).manifest
    canonical = canonical_manifest(manifest)
    digest = hashlib.sha256(canonical).hexdigest()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=30,
    ) as api:
        if args.repair_governance:
            state = json.loads(args.state.read_text(encoding="utf-8"))
            state.update(repair_governance(api, state))
            args.state.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {key: value for key, value in state.items() if key != "token"}
                )
            )
            return 0
        assert signing_secret is not None
        packages = request(api, "GET", "/v1/packages")
        package = next(
            (
                item
                for item in packages
                if item["name"] == package_name and item["version"] == manifest.version
            ),
            None,
        )
        if package is None:
            package = request(
                api,
                "POST",
                "/v1/packages",
                {
                    "manifest": manifest.model_dump(mode="json"),
                    "manifest_digest": digest,
                    "signature": hmac.new(
                        signing_secret.encode(), canonical, hashlib.sha256
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        if package["manifest_digest"] != digest:
            raise RuntimeError("Existing package digest differs from local source.")
        agents = request(api, "GET", "/v1/agents")
        if any(item["slug"] == profile["slug"] for item in agents):
            raise RuntimeError(
                "Observer identity already exists; refusing credential rotation."
            )
        registration = request(
            api,
            "POST",
            "/v1/agents",
            {
                "slug": profile["slug"],
                "display_name": profile["display_name"],
                "role": manifest.role,
                "machine": profile["machine"],
                "hermes_profile": package_name,
                "capabilities": manifest.required_capabilities,
                "risk_ceiling": 0,
            },
        )
        deployment = request(
            api,
            "POST",
            "/v1/packages/deployments",
            {
                "agent_id": registration["agent"]["id"],
                "package_id": package["id"],
                "deployed_by": "founder-operator",
            },
        )
        governance = ensure_governance(
            api, agent=registration["agent"], package=package
        )
    state = {
        "agent_id": registration["agent"]["id"],
        "slug": profile["slug"],
        "machine": profile["machine"],
        "token": registration["credential"]["token"],
        "package_id": package["id"],
        "deployment_id": deployment["id"],
        "manifest_digest": digest,
        "source_commit": args.source_commit,
        **governance,
    }
    args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: value for key, value in state.items() if key != "token"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
