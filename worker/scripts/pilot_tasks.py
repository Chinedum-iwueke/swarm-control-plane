#!/usr/bin/env python3
"""Create and verify the fixed Phase 1 pilot tasks."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

DEFAULT_API_URL = "http://100.112.117.59:8787"
AGENT_SLUG = "vm1-developer-coder"
_SENSITIVE_KEY = re.compile(
    r"(authorization|credential|lease_token|secret|token)",
    re.IGNORECASE,
)
_EXPECTED_TERMINAL_EVENTS = {
    "success": ("task_created", "task_leased", "task_started", "task_completed"),
    "failure": ("task_created", "task_leased", "task_started", "task_failed"),
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SENSITIVE_KEY.search(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _client() -> httpx.Client:
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token:
        raise RuntimeError("SWARM_ORCHESTRATOR_TOKEN is required.")
    api_url = os.environ.get("SWARM_API_URL", DEFAULT_API_URL).rstrip("/")
    return httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def _task_payload(kind: str) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    workflow = (
        "code-validation"
        if kind == "success"
        else "code-validation-failure"
    )
    return {
        "task_number": f"VM1-PILOT-{kind.upper()}-{timestamp}",
        "project": "swarm-control-plane",
        "task_type": "code_validation",
        "title": f"Restricted VM1 {kind} pilot",
        "objective": (
            "Validate the isolated swarm-control-plane worktree using the "
            f"server-local {workflow} workflow."
        ),
        "priority": 100,
        "risk_level": 0,
        "created_by": "phase-1-pilot",
        "input_contract": {
            "repository": "swarm-control-plane",
            "workflow": workflow,
            "base_ref": "main",
        },
        "expected_outputs": ["bounded workflow result", "workspace logs"],
        "acceptance_criteria": [
            "Only the named server-local workflow is executed."
        ],
        "approval_policy": {"pilot": True},
        "required_capabilities": ["python", "git", "testing"],
        "allowed_machines": ["vm1-developer"],
        "max_attempts": 1,
    }


def create_task(kind: str) -> int:
    with _client() as client:
        response = client.post("/v1/tasks", json=_task_payload(kind))
        response.raise_for_status()
        task = response.json()
    print(json.dumps({"id": task["id"], "task_number": task["task_number"]}))
    return 0


def _contains_sensitive_material(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _SENSITIVE_KEY.search(key) or _contains_sensitive_material(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_material(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "authorization:" in lowered or "bearer " in lowered
    return False


def verify_task(task_id: str, kind: str) -> int:
    with _client() as client:
        task_response = client.get(f"/v1/tasks/{task_id}")
        task_response.raise_for_status()
        detail = task_response.json()
        assigned_agent_id = detail["task"]["assigned_agent_id"]
        if not assigned_agent_id:
            raise RuntimeError("Task has no assigned agent.")
        agent_response = client.get(f"/v1/agents/{assigned_agent_id}")
        agent_response.raise_for_status()
        agent = agent_response.json()

    task = detail["task"]
    events = detail["events"]
    event_types = [event["event_type"] for event in events]
    required_order = _EXPECTED_TERMINAL_EVENTS[kind]
    positions = [event_types.index(event_type) for event_type in required_order]
    expected_status = "succeeded" if kind == "success" else "failed"
    result = task["result"] if kind == "success" else task["failure"]
    serialized_result = json.dumps(result, sort_keys=True)

    checks = {
        "status": task["status"] == expected_status,
        "agent": agent["slug"] == AGENT_SLUG,
        "attempt_count": task["attempt_count"] == 1,
        "event_order": positions == sorted(positions),
        "structured_output": isinstance(result, dict) and bool(result),
        "bounded_output": len(serialized_result.encode()) <= 65_536,
        "no_sensitive_material": not _contains_sensitive_material(detail),
    }
    output = {
        "task_id": task["id"],
        "task_number": task["task_number"],
        "status": task["status"],
        "assigned_agent": agent["slug"],
        "attempt_count": task["attempt_count"],
        "event_sequence": event_types,
        "checks": checks,
        "output": _redact(result),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("kind", choices=("success", "failure"))
    verify = subparsers.add_parser("verify")
    verify.add_argument("kind", choices=("success", "failure"))
    verify.add_argument("task_id")
    args = parser.parse_args()
    try:
        if args.command == "create":
            return create_task(args.kind)
        return verify_task(args.task_id, args.kind)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        print(f"pilot operation failed: {_redact(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
