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
    created = {"charters": 0, "grants": 0, "agents": 0}
    for row in deployments:
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
        charter = next((item for item in charters if item["manifest_digest"] == md), None)
        if not charter:
            response = client.post("/v1/agent-governance/charters", json={"agent_id": agent["id"], "version": "1.0.0", "manifest": manifest, "manifest_digest": md, "created_by": "founder-operator"})
            response.raise_for_status(); charter = response.json(); charters.append(charter); created["charters"] += 1
        if charter["status"] != "active":
            charter = client.post(f"/v1/agent-governance/charters/{charter['id']}/activate", json={"activated_by": "founder-operator"}).raise_for_status().json()
        for capability in pm["required_capabilities"]:
            current = next((item for item in grants if item["agent_id"] == agent["id"] and item["charter_id"] == charter["id"] and item["capability"] == capability and item["status"] == "active" and datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00")) > datetime.now(UTC)), None)
            if current: continue
            payload = {"agent_id": agent["id"], "charter_id": charter["id"], "capability": capability,
                "machine": agent["machine"], "task_types": pm["task_types"], "repositories": pm["repository_profile"]["repositories"],
                "risk_ceiling": manifest["risk_ceiling"], "accountable_owner": "company-operations", "granted_by": "founder-operator",
                "reason": f"AGT-001 active package {package['manifest_digest']}", "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat()}
            created_grant = client.post("/v1/agent-governance/grants", json=payload).raise_for_status().json()
            grants.append(created_grant); created["grants"] += 1
        created["agents"] += 1
    created["success"] = created["agents"] > 0
    print(json.dumps(created, indent=2))
    return 0 if created["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
