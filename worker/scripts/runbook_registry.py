#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx

from swarm_worker.infrastructure.packages import (
    canonical_manifest,
    load_runbook_package,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "list", "show", "promote"))
    parser.add_argument("--name")
    parser.add_argument("--package-id")
    parser.add_argument("--source-repository", default="swarm-control-plane")
    parser.add_argument("--source-commit")
    parser.add_argument("--state", choices=("draft", "rehearsed", "approved", "deployed"))
    parser.add_argument("--evidence-digest")
    parser.add_argument("--approval-reference")
    parser.add_argument("--actor", default="founder-operator")
    args = parser.parse_args()

    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=30) as client:
        if args.action == "list":
            response = client.get("/v1/runbook-packages")
        elif args.action == "show":
            _require(args, "package_id")
            response = client.get(f"/v1/runbook-packages/{args.package_id}")
        elif args.action == "promote":
            _require(args, "package_id", "state")
            response = client.post(
                f"/v1/runbook-packages/{args.package_id}/promotions",
                json={
                    "state": args.state,
                    "evidence_digest": args.evidence_digest,
                    "approval_reference": args.approval_reference,
                    "recorded_by": args.actor,
                },
            )
        else:
            _require(args, "name", "source_commit")
            secret = os.environ.get("SWARM_PACKAGE_SIGNING_SECRET")
            if not secret or len(secret) < 32:
                print("Protected package signing secret is required.", file=sys.stderr)
                return 2
            directory = Path(
                os.environ.get(
                    "SWARM_RUNBOOK_PACKAGE_DIRECTORY",
                    "/home/omenka/Projects/swarm-control-plane/worker/"
                    "runbook-packages",
                )
            )
            package = load_runbook_package(directory, args.name)
            document = canonical_manifest(package.manifest)
            response = client.post(
                "/v1/runbook-packages",
                json={
                    "manifest": package.manifest.model_dump(mode="json"),
                    "manifest_digest": hashlib.sha256(document).hexdigest(),
                    "signature": hmac.new(
                        secret.encode(), document, hashlib.sha256
                    ).hexdigest(),
                    "source_repository": args.source_repository,
                    "source_commit": args.source_commit,
                    "created_by": args.actor,
                },
            )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


def _require(args: argparse.Namespace, *names: str) -> None:
    missing = [f"--{name.replace('_', '-')}" for name in names if not getattr(args, name)]
    if missing:
        raise SystemExit("Required arguments: " + ", ".join(missing))


if __name__ == "__main__":
    raise SystemExit(main())
