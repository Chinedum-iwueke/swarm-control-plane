from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path

import httpx

from swarm_worker.role_package import canonical_manifest, load_role_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "vm1-research-memory-steward"


def request(
    client: httpx.Client, method: str, path: str, payload: dict | None = None
) -> dict | list:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap VM1 memory steward")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.state.exists() or args.env_file.exists():
        raise RuntimeError("Memory-steward state or environment file already exists.")
    signing_secret = os.environ["SWARM_PACKAGE_SIGNING_SECRET"]
    if len(signing_secret) < 32 or len(args.source_commit) != 40:
        raise RuntimeError("Signing secret and full source commit are required.")
    manifest = load_role_package(
        ROOT / f"role-packages/{PACKAGE}/manifest.yaml", ROOT / "workflows"
    ).manifest
    canonical = canonical_manifest(manifest)
    manifest_digest = hashlib.sha256(canonical).hexdigest()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=30,
    ) as api:
        packages = request(api, "GET", "/v1/packages")
        package = next(
            (
                item
                for item in packages
                if item["name"] == PACKAGE and item["version"] == manifest.version
            ),
            None,
        )
        if package is None:
            package = request(
                api,
                "POST",
                "/v1/packages",
                {
                    "manifest": manifest.model_dump(mode="json"),
                    "manifest_digest": manifest_digest,
                    "signature": hmac.new(
                        signing_secret.encode(), canonical, hashlib.sha256
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        registration = request(
            api,
            "POST",
            "/v1/agents",
            {
                "slug": "vm1-research-memory-steward",
                "display_name": "Research Memory Steward",
                "role": "Read-only Bulletproof research-memory synchronization",
                "machine": "vm1-developer",
                "hermes_profile": PACKAGE,
                "capabilities": manifest.required_capabilities,
                "risk_ceiling": 0,
            },
        )
        deployment = request(
            api,
            "POST",
            "/v1/packages/deployments",
            {
                "agent_id": registration["agent"]["id"],
                "package_id": package["id"],
                "deployed_by": "founder-operator",
            },
        )
    token = registration["credential"]["token"]
    state = {
        "agent_id": registration["agent"]["id"],
        "slug": registration["agent"]["slug"],
        "package_id": package["id"],
        "deployment_id": deployment["id"],
        "manifest_digest": manifest_digest,
        "source_commit": args.source_commit,
    }
    args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, sort_keys=True)
        stream.write("\n")
    environment = {
        "SWARM_API_URL": os.environ["SWARM_API_URL"].rstrip("/"),
        "SWARM_AGENT_TOKEN": token,
        "SWARM_AGENT_SLUG": state["slug"],
        "SWARM_MACHINE": "vm1-developer",
        "SWARM_WORKSPACE_ROOT": "/home/omenka/Projects/swarm-agent-workspaces",
        "SWARM_REPOSITORY_ROOT": "/home/omenka/Projects",
        "SWARM_WORKFLOW_DIRECTORY": str(ROOT / "workflows"),
        "SWARM_ROLE_PACKAGE_MANIFEST": str(
            ROOT / f"role-packages/{PACKAGE}/manifest.yaml"
        ),
    }
    args.env_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        args.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        for key, value in environment.items():
            if "\n" in value:
                raise RuntimeError(f"Invalid newline in {key}.")
            stream.write(f"{key}={value}\n")
    print(json.dumps(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
