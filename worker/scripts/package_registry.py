#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx

from swarm_worker.role_package import canonical_manifest, load_role_package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "deploy", "inventory", "revoke"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--source-repository")
    parser.add_argument("--source-commit")
    parser.add_argument("--actor", default="founder-operator")
    parser.add_argument("--agent-id")
    parser.add_argument("--package-id")
    parser.add_argument("--deployment-id")
    args = parser.parse_args()

    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=30) as client:
        if args.action == "inventory":
            response = client.get("/v1/packages/deployments")
        elif args.action == "deploy":
            _require(args, "agent_id", "package_id")
            response = client.post(
                "/v1/packages/deployments",
                json={
                    "agent_id": args.agent_id,
                    "package_id": args.package_id,
                    "deployed_by": args.actor,
                },
            )
        elif args.action == "revoke":
            _require(args, "deployment_id")
            response = client.post(
                f"/v1/packages/deployments/{args.deployment_id}/revoke"
            )
        else:
            _require(args, "manifest", "source_repository", "source_commit")
            signing_secret = os.environ.get("SWARM_PACKAGE_SIGNING_SECRET")
            workflow_directory = Path(
                os.environ.get(
                    "SWARM_WORKFLOW_DIRECTORY",
                    "/home/omenka/Projects/swarm-control-plane/worker/workflows",
                )
            )
            if not signing_secret or len(signing_secret) < 32:
                print("Protected package signing secret is required.", file=sys.stderr)
                return 2
            package = load_role_package(args.manifest, workflow_directory)
            document = canonical_manifest(package.manifest)
            response = client.post(
                "/v1/packages",
                json={
                    "manifest": package.manifest.model_dump(mode="json"),
                    "manifest_digest": hashlib.sha256(document).hexdigest(),
                    "signature": hmac.new(
                        signing_secret.encode(), document, hashlib.sha256
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
