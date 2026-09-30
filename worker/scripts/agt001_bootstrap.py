#!/usr/bin/env python3
"""Backfill least-privilege charters and grants for active package deployments."""
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def workload_scopes(package_manifest: dict) -> list[str]:
    scopes = {"identity:read", "heartbeat:write", "control:read", "package:read"}
    task_types = set(package_manifest.get("task_types", []))
    if task_types:
        scopes |= {"task:lease", "task:execute"}
    if any(item.startswith("infrastructure_") for item in task_types):
        scopes.add("infrastructure:broker")
    if "founder_request" in task_types:
        scopes.add("proposal:write")
    if any(item.startswith("research_") for item in task_types):
        scopes.add("research:write")
    if "fleet_observation" in task_types:
        scopes.add("fleet:write")
    if "operational_memory" in task_types:
        scopes.add("notes:write")
    return sorted(scopes)


def next_identity_version(identities: list[dict], agent_id: str) -> str:
    used = {
        item["version"] for item in identities if item["agent_id"] == agent_id
    }
    revision = 0
    while f"1.0.{revision}" in used:
        revision += 1
    return f"1.0.{revision}"


def charter_covers_package(charter: dict, agent: dict, package_manifest: dict) -> bool:
    manifest = charter["manifest"]
    return (
        charter["agent_id"] == agent["id"]
        and charter["status"] == "active"
        and agent["machine"] in manifest["allowed_machines"]
        and set(package_manifest["required_capabilities"]).issubset(
            manifest["capabilities"]
        )
        and set(package_manifest["task_types"]).issubset(
            manifest["allowed_task_types"]
        )
        and set(package_manifest["repository_profile"]["repositories"]).issubset(
            manifest["allowed_repositories"]
        )
        and package_manifest["risk_ceiling"] <= manifest["risk_ceiling"]
    )


def main() -> int:
    base = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token and os.environ.get("SWARM_ORCHESTRATOR_TOKEN_FILE"):
        token = Path(os.environ["SWARM_ORCHESTRATOR_TOKEN_FILE"]).read_text().strip()
    client = httpx.Client(base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    agents = {item["id"]: item for item in client.get("/v1/agents").raise_for_status().json()}
    deployments = client.get("/v1/packages/deployments").raise_for_status().json()
    charters = client.get("/v1/agent-governance/charters").raise_for_status().json()
    grants = client.get("/v1/agent-governance/grants").raise_for_status().json()
    identities = client.get("/v1/workload-identities").raise_for_status().json()
    created = {
        "charters": 0,
        "grants": 0,
        "identities": 0,
        "credentials_bound": 0,
        "agents": 0,
    }
    latest = {}
    for row in deployments:
        if row["deployment"]["is_active"]:
            latest[row["deployment"]["agent_id"]] = row
    for row in latest.values():
        if not row["deployment"]["is_active"]:
            continue
        agent = agents.get(row["deployment"]["agent_id"])
        if not agent or not agent["is_enabled"]:
            continue
        package = row["package"]; pm = package["manifest"]
        manifest = {"schema_version": "agent-charter-v1.0.0", "role": pm["role"],
            "responsibilities": ["Execute only digest-bound work inside the active role package."],
            "capabilities": pm["required_capabilities"], "allowed_machines": [agent["machine"]],
            "allowed_task_types": pm["task_types"], "allowed_repositories": pm["repository_profile"]["repositories"],
            "risk_ceiling": min(agent["risk_ceiling"], pm["risk_ceiling"]), "accountable_owner": "company-operations",
            "conflicts": [], "forbidden_actions": ["capital-allocation", "order-placement", "live-trading"]}
        md = digest(manifest)
        charter = next(
            (
                item
                for item in charters
                if charter_covers_package(item, agent, pm)
            ),
            None,
        )
        if charter is None:
            charter = next(
                (
                    item
                    for item in charters
                    if item["agent_id"] == agent["id"]
                    and item["manifest_digest"] == md
                ),
                None,
            )
        if not charter:
            version = f"1.0.{sum(item['agent_id'] == agent['id'] for item in charters)}"
            response = client.post("/v1/agent-governance/charters", json={"agent_id": agent["id"], "version": version, "manifest": manifest, "manifest_digest": md, "created_by": "founder-operator"})
            response.raise_for_status(); charter = response.json(); charters.append(charter); created["charters"] += 1
        if charter["status"] != "active":
            charter = client.post(f"/v1/agent-governance/charters/{charter['id']}/activate", json={"activated_by": "founder-operator"}).raise_for_status().json()
        for capability in pm["required_capabilities"]:
            current = next((item for item in grants if item["agent_id"] == agent["id"] and item["charter_id"] == charter["id"] and item["package_id"] == package["id"] and item["capability"] == capability and item["status"] == "active" and datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00")) > datetime.now(UTC)), None)
            if current: continue
            payload = {"agent_id": agent["id"], "charter_id": charter["id"], "package_id": package["id"], "capability": capability,
                "machine": agent["machine"], "task_types": pm["task_types"], "repositories": pm["repository_profile"]["repositories"],
                "risk_ceiling": manifest["risk_ceiling"], "accountable_owner": "company-operations", "granted_by": "founder-operator",
                "reason": f"AGT-001 active package {package['manifest_digest']}", "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat()}
            created_grant = client.post("/v1/agent-governance/grants", json=payload).raise_for_status().json()
            grants.append(created_grant); created["grants"] += 1
        identity = next(
            (
                item
                for item in identities
                if item["agent_id"] == agent["id"]
                and item["charter_id"] == charter["id"]
                and item["package_id"] == package["id"]
                and item["status"] == "active"
                and datetime.fromisoformat(
                    item["expires_at"].replace("Z", "+00:00")
                )
                > datetime.now(UTC)
            ),
            None,
        )
        if identity is None:
            identity = client.post(
                "/v1/workload-identities",
                json={
                    "agent_id": agent["id"],
                    "charter_id": charter["id"],
                    "package_id": package["id"],
                    "version": next_identity_version(identities, agent["id"]),
                    "audience": "invariance-control-plane",
                    "scopes": workload_scopes(pm),
                    "accountable_owner": manifest["accountable_owner"],
                    "expires_at": (
                        datetime.now(UTC) + timedelta(days=365)
                    ).isoformat(),
                    "created_by": "founder-operator",
                },
            ).raise_for_status().json()
            identities.append(identity)
            created["identities"] += 1
        binding = client.post(
            f"/v1/workload-identities/{identity['id']}/bind-credentials",
            json={"actor": "founder-operator"},
        ).raise_for_status().json()
        created["credentials_bound"] += binding["bound_credentials"]
        created["agents"] += 1
    created["success"] = created["agents"] > 0
    print(json.dumps(created, indent=2))
    return 0 if created["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
