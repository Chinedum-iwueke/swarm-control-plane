#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import UTC, datetime

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("create-observation", "create-restart", "status")
    )
    parser.add_argument("--task-id")
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
        if args.action == "status":
            if not args.task_id:
                parser.error("status requires --task-id")
            response = client.get(f"/v1/tasks/{args.task_id}")
        else:
            restart = args.action == "create-restart"
            operation = (
                "restart-control-plane-api" if restart else "observe-control-plane"
            )
            task_type = (
                "infrastructure_operation" if restart else "infrastructure_observation"
            )
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            response = client.post(
                "/v1/tasks",
                json={
                    "task_number": (
                        f"VM2-RESTART-{timestamp}"
                        if restart
                        else f"VM2-OBSERVE-{timestamp}"
                    ),
                    "project": "swarm-control-plane",
                    "task_type": task_type,
                    "title": (
                        "Approved controlled VM2 API restart"
                        if restart
                        else "Observe VM2 control-plane infrastructure"
                    ),
                    "objective": (
                        "Restart only the control-plane API with pre/post checks."
                        if restart
                        else "Collect read-only VM2 infrastructure health evidence."
                    ),
                    "priority": 70,
                    "risk_level": 3 if restart else 0,
                    "created_by": "founder-operator",
                    "input_contract": {
                        "runbook": "vm2-infrastructure",
                        "runbook_version": "1.0.0",
                        "operation": operation,
                        "target": "vm2-control-plane",
                        "parameters": {},
                    },
                    "expected_outputs": ["infrastructure-evidence.json"],
                    "acceptance_criteria": [
                        (
                            "Pre-state and post-state are healthy."
                            if restart
                            else "Docker, PostgreSQL, Redis, and API health are recorded."
                        ),
                        "Evidence digest is registered.",
                    ],
                    "approval_policy": (
                        {"kind": "explicit", "risk": 3}
                        if restart
                        else {"kind": "automatic", "risk": 0}
                    ),
                    "approval_required": restart,
                    "required_capabilities": [
                        "infrastructure-observation",
                        "service-health",
                        "controlled-restart",
                    ],
                    "allowed_machines": ["vm2-deployment"],
                    "max_attempts": 1,
                },
            )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
