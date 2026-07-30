#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-output", type=Path, required=True)
    args = parser.parse_args()
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    if args.token_output.exists():
        print("Token output already exists.", file=sys.stderr)
        return 2
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        response = client.post(
            "/v1/agents",
            json={
                "slug": "vm1-research-runner",
                "display_name": "VM1 Research Runner",
                "role": "Restricted reproducible experiment runner",
                "machine": "vm1-developer",
                "hermes_profile": "restricted-research",
                "capabilities": [
                    "git",
                    "python",
                    "backtesting",
                    "research-audit",
                ],
                "risk_ceiling": 1,
            },
        )
        response.raise_for_status()
        payload = response.json()
    raw_token = payload["credential"]["token"]
    descriptor = os.open(
        args.token_output,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(raw_token)
    print(
        json.dumps(
            {
                "agent_id": payload["agent"]["id"],
                "slug": payload["agent"]["slug"],
                "machine": payload["agent"]["machine"],
                "token_output": str(args.token_output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
