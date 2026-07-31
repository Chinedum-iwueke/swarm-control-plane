#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import httpx

PACKAGE_NAME = "vm2-platform-operations"
PACKAGE_VERSION = "1.0.0"
SERVICES = ("api", "postgres", "pgbouncer", "redis")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("health", "restart"))
    parser.add_argument("--service", required=True, choices=SERVICES)
    args = parser.parse_args()
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        package = _approved_package(client)
        restart = args.action == "restart"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        response = client.post(
            "/v1/tasks",
            json={
                "task_number": f"VM2-{args.action.upper()}-{timestamp}",
                "project": "swarm-control-plane",
                "task_type": (
                    "infrastructure_operation"
                    if restart
                    else "infrastructure_observation"
                ),
                "title": f"VM2 {args.service} {args.action}",
                "objective": (
                    f"Restart only the allowlisted {args.service} service with "
                    "pre/post verification and fixed rollback."
                    if restart
                    else f"Collect bounded health evidence for {args.service}."
                ),
                "priority": 70,
                "risk_level": 3 if restart else 0,
                "created_by": "founder-operator",
                "input_contract": {
                    "runbook": PACKAGE_NAME,
                    "runbook_version": PACKAGE_VERSION,
                    "operation": (
                        "restart-docker-service"
                        if restart
                        else "verify-docker-service"
                    ),
                    "target": "vm2-production",
                    "parameters": {"service": args.service},
                    "package_name": PACKAGE_NAME,
                    "package_version": PACKAGE_VERSION,
                    "package_digest": package["manifest_digest"],
                },
                "expected_outputs": ["infrastructure-evidence.json"],
                "acceptance_criteria": [
                    "The exact approved package digest is used.",
                    "Post-state is healthy and evidence is registered.",
                    "Rollback is recorded if restart verification fails.",
                ],
                "approval_policy": {
                    "kind": "explicit" if restart else "automatic",
                    "risk": 3 if restart else 0,
                },
                "approval_required": restart,
                "required_capabilities": [
                    "deployment-architecture",
                    "infrastructure-observation",
                    "service-health",
                ],
                "allowed_machines": ["vm2-deployment"],
                "max_attempts": 1,
            },
        )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


def _approved_package(client: httpx.Client) -> dict:
    response = client.get("/v1/runbook-packages")
    response.raise_for_status()
    matches = [
        item
        for item in response.json()
        if item["name"] == PACKAGE_NAME and item["version"] == PACKAGE_VERSION
    ]
    if len(matches) != 1:
        raise SystemExit("The exact runbook package is not registered.")
    package = matches[0]
    detail = client.get(f"/v1/runbook-packages/{package['id']}")
    detail.raise_for_status()
    promotions = detail.json()["promotions"]
    if not promotions or promotions[-1]["state"] not in {"approved", "deployed"}:
        raise SystemExit("The exact runbook package is not approved.")
    return package


if __name__ == "__main__":
    raise SystemExit(main())
