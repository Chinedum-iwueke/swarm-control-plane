#!/usr/bin/env python3
"""Create exact-authority workload identities and activate fail-closed enforcement."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

UTC = timezone.utc


def scopes(manifest: dict) -> list[str]:
    result = {"identity:read", "heartbeat:write", "control:read", "package:read"}
    task_types = set(manifest.get("task_types", []))
    if task_types:
        result |= {"task:lease", "task:execute"}
    if any(item.startswith("infrastructure_") for item in task_types):
        result.add("infrastructure:broker")
    if "founder_request" in task_types:
        result.add("proposal:write")
    if any(item.startswith("research_") for item in task_types):
        result.add("research:write")
    if "fleet_observation" in task_types:
        result.add("fleet:write")
    if "operational_memory" in task_types:
        result.add("notes:write")
    return sorted(result)


def main() -> int:
    base = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token and os.environ.get("SWARM_ORCHESTRATOR_TOKEN_FILE"):
        token = Path(os.environ["SWARM_ORCHESTRATOR_TOKEN_FILE"]).read_text().strip()
    client = httpx.Client(
        base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=90
    )
    agents = {
        item["id"]: item for item in client.get("/v1/agents").raise_for_status().json()
    }
    active = [
        item
        for item in client.get("/v1/packages/deployments").raise_for_status().json()
        if item["deployment"]["is_active"]
    ]
    latest = {}
    for item in active:
        key = item["deployment"]["agent_id"]
        if (
            key not in latest
            or item["deployment"]["deployed_at"]
            > latest[key]["deployment"]["deployed_at"]
        ):
            latest[key] = item
    deployments = list(latest.values())
    charters = client.get("/v1/agent-governance/charters").raise_for_status().json()
    identities = client.get("/v1/workload-identities").raise_for_status().json()
    report = {"created": 0, "existing": 0, "credentials_bound": 0, "identities": []}
    for row in deployments:
        agent = agents.get(row["deployment"]["agent_id"])
        package = row["package"]
        if not agent or not agent["is_enabled"]:
            continue
        charter = next(
            (
                item
                for item in reversed(charters)
                if item["agent_id"] == agent["id"] and item["status"] == "active"
            ),
            None,
        )
        if not charter:
            raise RuntimeError(f"No active charter for {agent['slug']}")
        identity = next(
            (
                item
                for item in identities
                if item["agent_id"] == agent["id"]
                and item["package_id"] == package["id"]
                and item["status"] == "active"
            ),
            None,
        )
        if not identity:
            payload = {
                "agent_id": agent["id"],
                "charter_id": charter["id"],
                "package_id": package["id"],
                "version": f"1.0.{sum(item['agent_id'] == agent['id'] for item in identities)}",
                "audience": "invariance-control-plane",
                "scopes": scopes(package["manifest"]),
                "accountable_owner": "company-operations",
                "expires_at": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
                "created_by": "founder-operator",
            }
            identity = (
                client.post("/v1/workload-identities", json=payload)
                .raise_for_status()
                .json()
            )
            identities.append(identity)
            report["created"] += 1
        else:
            report["existing"] += 1
        bound = (
            client.post(
                f"/v1/workload-identities/{identity['id']}/bind-credentials",
                json={"actor": "founder-operator"},
            )
            .raise_for_status()
            .json()
        )
        report["credentials_bound"] += bound["bound_credentials"]
        report["identities"].append(
            {
                "agent": agent["slug"],
                "identity_id": identity["id"],
                "manifest_digest": identity["manifest_digest"],
                "scopes": identity["scopes"],
            }
        )
    report["enforcement"] = (
        client.post(
            "/v1/workload-identities/enforcement/activate",
            json={"activated_by": "founder-operator"},
        )
        .raise_for_status()
        .json()
    )
    report["report_digest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
