#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx
import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "list", "status", "resume"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--mission-id")
    parser.add_argument("--task-id")
    parser.add_argument("--reason")
    parser.add_argument("--actor", default="founder-operator")
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
        if args.action == "list":
            response = client.get("/v1/missions")
        elif args.action == "status":
            if not args.mission_id:
                parser.error("status requires --mission-id")
            response = client.get(f"/v1/missions/{args.mission_id}")
        elif args.action == "resume":
            if not args.task_id or not args.reason:
                parser.error("resume requires --task-id and --reason")
            response = client.post(
                f"/v1/tasks/{args.task_id}/resume",
                json={
                    "requested_by": args.actor,
                    "reason": args.reason,
                },
            )
        else:
            if not args.manifest:
                parser.error("create requires --manifest")
            document = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                parser.error("manifest must contain a YAML mapping")
            approval_secret = os.environ.get("SWARM_MISSION_APPROVAL_SECRET")
            if not approval_secret or len(approval_secret) < 32:
                print(
                    "Protected mission approval secret is required.",
                    file=sys.stderr,
                )
                return 2
            canonical = json.dumps(
                document,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            response = client.post(
                "/v1/missions",
                json={
                    "manifest": document,
                    "created_by": args.actor,
                    "approval_signature": hmac.new(
                        approval_secret.encode(),
                        canonical,
                        hashlib.sha256,
                    ).hexdigest(),
                },
            )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
