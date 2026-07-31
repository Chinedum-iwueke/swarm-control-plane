#!/usr/bin/env python3
import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "approvals",
            "approve",
            "reject",
            "revoke",
            "rearm",
            "events",
            "artifacts",
        ),
    )
    parser.add_argument("--approval-id")
    parser.add_argument("--task-id")
    parser.add_argument("--reason")
    parser.add_argument("--actor", default="founder-operator")
    parser.add_argument("--expires-in-seconds", type=int, default=3600)
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
        if args.action == "approvals":
            response = client.get("/v1/approvals")
        elif args.action == "artifacts":
            params = {"task_id": args.task_id} if args.task_id else {}
            response = client.get("/v1/artifacts", params=params)
        elif args.action == "events":
            _require(args.approval_id, "--approval-id")
            response = client.get(f"/v1/approvals/{args.approval_id}/events")
        elif args.action == "rearm":
            _require(args.task_id, "--task-id")
            _require(args.reason, "--reason")
            response = client.post(
                f"/v1/tasks/{args.task_id}/rearm-approval",
                json={"requested_by": args.actor, "reason": args.reason},
            )
        else:
            _require(args.approval_id, "--approval-id")
            _require(args.reason, "--reason")
            response = client.post(
                f"/v1/approvals/{args.approval_id}/{args.action}",
                json={
                    "actor": args.actor,
                    "reason": args.reason,
                    "expires_in_seconds": args.expires_in_seconds,
                },
            )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


def _require(value: str | None, flag: str) -> None:
    if not value:
        raise SystemExit(f"{flag} is required.")


if __name__ == "__main__":
    raise SystemExit(main())
