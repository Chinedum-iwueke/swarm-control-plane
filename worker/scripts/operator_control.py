#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pause", "resume", "status", "metrics"))
    parser.add_argument("--scope", choices=("global", "machine", "agent"))
    parser.add_argument("--key")
    parser.add_argument("--reason")
    parser.add_argument("--actor", default="founder-operator")
    args = parser.parse_args()

    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    if not token or not api_url:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=30.0) as client:
        if args.action == "status":
            response = client.get("/v1/control/scopes")
        elif args.action == "metrics":
            response = client.get("/v1/metrics")
        else:
            if not args.scope or not args.key or not args.reason:
                parser.error("pause/resume require --scope, --key, and --reason")
            response = client.post(
                f"/v1/control/{args.action}",
                json={
                    "scope_type": args.scope,
                    "scope_key": args.key,
                    "reason": args.reason,
                    "actor": args.actor,
                },
            )
        response.raise_for_status()
        if args.action == "metrics":
            print(response.text, end="")
        else:
            print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
