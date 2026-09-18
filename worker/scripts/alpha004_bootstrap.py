#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from alpha002_bootstrap import (
    WORKLOAD_SCOPES,
    atomic_write,
    call,
    digest,
    ensure_workload_identity,
)

from swarm_worker.role_package import canonical_manifest, load_role_package

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "intelligence": {
        "package": "m14b-research-intelligence-director",
        "slug": "vm1-alpha004-research-intelligence-director",
        "display": "VM1 Research Intelligence Director",
        "environment": "/etc/invariance-swarm/alpha004-intelligence.env",
        "state": "/etc/invariance-swarm/alpha004-intelligence-state.json",
    },
    "researcher": {
        "package": "m13-senior-research-specialist",
        "slug": "vm1-alpha004-senior-researcher",
        "display": "VM1 Senior Quantitative Researcher",
        "environment": "/etc/invariance-swarm/alpha004-researcher.env",
        "state": "/etc/invariance-swarm/alpha004-researcher-state.json",
    },
    "representation": {
        "package": "alpha-data-representation-scientist",
        "slug": "vm1-alpha-data-representation-scientist",
        "display": "VM1 Alpha Data Representation Scientist",
        "environment": "/etc/invariance-swarm/alpha004-representation.env",
        "state": "/etc/invariance-swarm/alpha004-representation-state.json",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=sorted(PROFILES))
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if len(args.source_commit) != 40:
        raise RuntimeError("A full control-plane source commit is required.")
    profile = PROFILES[args.profile]
    state_path = Path(profile["state"])
    environment_path = Path(profile["environment"])
    package_name = profile["package"]
    manifest = load_role_package(
        ROOT / "role-packages" / package_name / "manifest.yaml", ROOT / "workflows"
    ).manifest
    canonical = canonical_manifest(manifest)
    manifest_digest = hashlib.sha256(canonical).hexdigest()
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"), headers=headers, timeout=60
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
                        os.environ["SWARM_PACKAGE_SIGNING_SECRET"].encode(),
                        canonical,
                        hashlib.sha256,
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        agents = call(api, "GET", "/v1/agents")
        agent = next((item for item in agents if item["slug"] == profile["slug"]), None)
        registration = None
        if agent is None:
            registration = call(
                api,
                "POST",
                "/v1/agents",
                {
                    "slug": profile["slug"],
                    "display_name": profile["display"],
                    "role": manifest.role,
                    "machine": "vm1-developer",
                    "hermes_profile": package_name,
                    "capabilities": manifest.required_capabilities,
                    "risk_ceiling": 0,
                },
            )
            agent = registration["agent"]
        deployment = call(
            api,
            "POST",
            "/v1/packages/deployments",
            {
                "agent_id": agent["id"],
                "package_id": package["id"],
                "deployed_by": "founder-operator",
            },
        )
        charter_manifest = {
            "schema_version": "agent-charter-v1.0.0",
            "role": manifest.role,
            "responsibilities": [
                "Perform one bounded ALPHA-004 evidence or hypothesis stage."
            ],
            "capabilities": manifest.required_capabilities,
            "allowed_machines": ["vm1-developer"],
            "allowed_task_types": ["alpha_discovery"],
            "allowed_repositories": ["swarm-control-plane"],
            "risk_ceiling": 0,
            "accountable_owner": "senior-quantitative-research",
            "conflicts": ["independent-evaluation"],
            "forbidden_actions": [
                "capital-allocation",
                "order-placement",
                "live-trading",
                "shadow-admission",
                "code-change",
                "self-evaluation",
            ],
        }
        charter = call(
            api,
            "POST",
            "/v1/agent-governance/charters",
            {
                "agent_id": agent["id"],
                "version": "1.1.0",
                "manifest": charter_manifest,
                "manifest_digest": digest(charter_manifest),
                "created_by": "founder-operator",
            },
        )
        if charter["status"] != "active":
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
                    "agent_id": agent["id"],
                    "charter_id": charter["id"],
                    "package_id": package["id"],
                    "capability": capability,
                    "machine": "vm1-developer",
                    "task_types": ["alpha_discovery"],
                    "repositories": ["swarm-control-plane"],
                    "risk_ceiling": 0,
                    "accountable_owner": "senior-quantitative-research",
                    "granted_by": "founder-operator",
                    "reason": "ALPHA-004 bounded no-capital discovery",
                    "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                },
            )
            grant_ids.append(grant["id"])
        state = {
            "agent_id": agent["id"],
            "slug": profile["slug"],
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
    if registration is None:
        if not environment_path.exists():
            raise RuntimeError(
                "Existing agent has no local credential; rotate it explicitly."
            )
    else:
        environment = "\n".join(
            [
                f"SWARM_API_URL={os.environ['SWARM_API_URL']}",
                f"SWARM_AGENT_TOKEN={registration['credential']['token']}",
                f"SWARM_AGENT_SLUG={profile['slug']}",
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
        atomic_write(environment_path, environment)
    atomic_write(state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
