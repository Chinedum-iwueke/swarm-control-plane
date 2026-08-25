#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/var/lib/invariance-swarm/agt001/report.json")
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token and os.environ.get("SWARM_ORCHESTRATOR_TOKEN_FILE"):
        token = Path(os.environ["SWARM_ORCHESTRATOR_TOKEN_FILE"]).read_text().strip()
    client = httpx.Client(base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    agents = client.get("/v1/agents").raise_for_status().json()
    deployments = client.get("/v1/packages/deployments").raise_for_status().json()
    chosen = next((row for row in deployments if row["deployment"]["is_active"] and
                   next((a for a in agents if a["id"] == row["deployment"]["agent_id"] and a["is_enabled"]), None)), None)
    if not chosen:
        raise RuntimeError("No enabled agent with an active role package is available.")
    agent = next(a for a in agents if a["id"] == chosen["deployment"]["agent_id"])
    package = chosen["package"]; pm = package["manifest"]
    capability = pm["required_capabilities"][0]; task_type = pm["task_types"][0]
    manifest = {"schema_version": "agent-charter-v1.0.0", "role": pm["role"],
        "responsibilities": ["Execute only digest-bound work inside the active role package."],
        "capabilities": pm["required_capabilities"], "allowed_machines": [agent["machine"]],
        "allowed_task_types": pm["task_types"], "allowed_repositories": pm["repository_profile"]["repositories"],
        "risk_ceiling": min(agent["risk_ceiling"], pm["risk_ceiling"]), "accountable_owner": "company-operations",
        "conflicts": [], "forbidden_actions": ["capital-allocation", "order-placement", "live-trading"]}
    charter_digest = digest(manifest)
    charters = client.get("/v1/agent-governance/charters").raise_for_status().json()
    charter = next((item for item in charters if item["manifest_digest"] == charter_digest), None)
    if not charter:
        response = client.post("/v1/agent-governance/charters", json={"agent_id": agent["id"], "version": "1.0.0",
            "manifest": manifest, "manifest_digest": charter_digest, "created_by": "founder-operator"})
        response.raise_for_status(); charter = response.json()
    if charter["status"] != "active":
        charter = client.post(f"/v1/agent-governance/charters/{charter['id']}/activate", json={"activated_by": "founder-operator"}).raise_for_status().json()
    expiry = datetime.now(UTC) + timedelta(hours=1)
    grant_payload = {"agent_id": agent["id"], "charter_id": charter["id"], "capability": capability,
        "machine": agent["machine"], "task_types": [task_type], "repositories": pm["repository_profile"]["repositories"],
        "risk_ceiling": manifest["risk_ceiling"], "accountable_owner": "company-operations", "granted_by": "founder-operator",
        "reason": "AGT-001 bounded production replay", "expires_at": expiry.isoformat()}
    grant = client.post("/v1/agent-governance/grants", json=grant_payload).raise_for_status().json()
    request = {"capability": capability, "machine": agent["machine"], "task_type": task_type,
               "repository": pm["repository_profile"]["repositories"][0] if pm["repository_profile"]["repositories"] else None,
               "risk_level": manifest["risk_ceiling"]}
    allowed = client.post(f"/v1/agent-governance/agents/{agent['id']}/resolve", json=request).raise_for_status().json()
    revoked = client.post(f"/v1/agent-governance/grants/{grant['id']}/revoke",
                          json={"revoked_by": "founder-operator", "reason": "AGT-001 rollback proof"}).raise_for_status().json()
    denied = client.post(f"/v1/agent-governance/agents/{agent['id']}/resolve", json=request).raise_for_status().json()
    report = {"schema_version": "agt001-report-v1.0.0", "agent_id": agent["id"], "package_digest": package["manifest_digest"],
              "charter_digest": charter_digest, "grant_digest": grant["record_digest"], "allowed_snapshot": allowed,
              "revoked_status": revoked["status"], "denied_snapshot": denied,
              "capital_or_order_authority": False, "success": allowed["allowed"] and not denied["allowed"]}
    report["report_digest"] = digest(report)
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, indent=2) + "\n"); output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
