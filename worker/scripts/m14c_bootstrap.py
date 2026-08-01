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
PACKAGE = "vm1-operational-memory-steward"
SLUG = "vm1-operational-memory-steward"


def request(
    client: httpx.Client, method: str, path: str, payload: dict | None = None
) -> dict | list:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the M14C Steward identity")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--recover-existing", action="store_true")
    args = parser.parse_args()
    if args.state.exists():
        raise RuntimeError(
            "Steward state already exists; refusing credential rotation."
        )
    signing_secret = os.environ["SWARM_PACKAGE_SIGNING_SECRET"]
    if len(signing_secret) < 32 or len(args.source_commit) != 40:
        raise RuntimeError("Protected signing secret and full commit are required.")
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
        if package["manifest_digest"] != manifest_digest:
            raise RuntimeError("Existing Steward package digest differs.")
        agent_document = {
            "slug": SLUG,
            "display_name": "Operational Memory Steward",
            "role": "Non-executing operational observation and evidence steward",
            "machine": "vm1-developer",
            "hermes_profile": PACKAGE,
            "capabilities": manifest.required_capabilities,
            "risk_ceiling": 0,
        }
        agents = request(api, "GET", "/v1/agents")
        existing_agent = next((item for item in agents if item["slug"] == SLUG), None)
        if existing_agent is None:
            registration = request(api, "POST", "/v1/agents", agent_document)
        else:
            expected = {
                "machine": agent_document["machine"],
                "hermes_profile": agent_document["hermes_profile"],
                "capabilities": sorted(agent_document["capabilities"]),
                "risk_ceiling": 0,
            }
            actual = {
                "machine": existing_agent["machine"],
                "hermes_profile": existing_agent["hermes_profile"],
                "capabilities": sorted(existing_agent["capabilities"]),
                "risk_ceiling": existing_agent["risk_ceiling"],
            }
            if actual != expected:
                raise RuntimeError("Existing Steward identity does not match policy.")
            if not args.recover_existing:
                raise RuntimeError(
                    "Steward identity already exists; use --recover-existing only "
                    "after verifying its credential is unavailable."
                )
            registration = request(
                api,
                "POST",
                f"/v1/agents/{existing_agent['id']}/credentials/rotate",
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
    state = {
        "agent_id": registration["agent"]["id"],
        "slug": SLUG,
        "token": registration["credential"]["token"],
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
    print(json.dumps({k: v for k, v in state.items() if k != "token"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
