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
PROFILES = {
    "exec1": {
        "package": "exec1-fleet-observer",
        "slug": "exec1-fleet-observer",
        "display_name": "EXEC1 Fleet Observer",
        "machine": "exec1-execution",
    },
    "vm1": {
        "package": "vm1-fleet-observer",
        "slug": "vm1-fleet-observer",
        "display_name": "VM1 Fleet Observer",
        "machine": "vm1-developer",
    },
    "vm2": {
        "package": "vm2-fleet-observer",
        "slug": "vm2-fleet-observer",
        "display_name": "VM2 Fleet Observer",
        "machine": "vm2-deployment",
    },
}


def request(client: httpx.Client, method: str, path: str, payload: dict | None = None):
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap one OPS-004 fleet observer")
    parser.add_argument("profile", choices=sorted(PROFILES))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.state.exists():
        raise RuntimeError("State already exists; refusing implicit credential rotation.")
    if len(args.source_commit) != 40:
        raise RuntimeError("A full source commit is required.")
    signing_secret = os.environ["SWARM_PACKAGE_SIGNING_SECRET"]
    if len(signing_secret) < 32:
        raise RuntimeError("Protected package signing secret is unavailable.")
    profile = PROFILES[args.profile]
    package_name = profile["package"]
    manifest = load_role_package(
        ROOT / "role-packages" / package_name / "manifest.yaml", ROOT / "workflows"
    ).manifest
    canonical = canonical_manifest(manifest)
    digest = hashlib.sha256(canonical).hexdigest()
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
                if item["name"] == package_name and item["version"] == manifest.version
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
                    "manifest_digest": digest,
                    "signature": hmac.new(
                        signing_secret.encode(), canonical, hashlib.sha256
                    ).hexdigest(),
                    "source_repository": "swarm-control-plane",
                    "source_commit": args.source_commit,
                    "created_by": "founder-operator",
                },
            )
        if package["manifest_digest"] != digest:
            raise RuntimeError("Existing package digest differs from local source.")
        agents = request(api, "GET", "/v1/agents")
        if any(item["slug"] == profile["slug"] for item in agents):
            raise RuntimeError("Observer identity already exists; refusing credential rotation.")
        registration = request(
            api,
            "POST",
            "/v1/agents",
            {
                "slug": profile["slug"],
                "display_name": profile["display_name"],
                "role": manifest.role,
                "machine": profile["machine"],
                "hermes_profile": package_name,
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
    state = {
        "agent_id": registration["agent"]["id"],
        "slug": profile["slug"],
        "machine": profile["machine"],
        "token": registration["credential"]["token"],
        "package_id": package["id"],
        "deployment_id": deployment["id"],
        "manifest_digest": digest,
        "source_commit": args.source_commit,
    }
    args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: value for key, value in state.items() if key != "token"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
