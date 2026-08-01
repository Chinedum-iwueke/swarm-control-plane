from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import httpx

from swarm_worker.role_package import canonical_manifest, load_role_package

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    "senior": (
        "m13-senior-research-specialist",
        ["research-proposal", "knowledge-retrieval", "prior-art"],
    ),
    "specification": (
        "m13-experiment-specification",
        ["experiment-specification", "snapshot-read", "manifest-lock"],
    ),
    "execution": (
        "m13-research-execution",
        ["git", "python", "backtesting", "research-execution"],
    ),
    "statistical": (
        "m13-statistical-reviewer",
        ["statistical-review", "reproduction", "trial-aware-analysis"],
    ),
    "adversarial": (
        "m13-adversarial-auditor",
        ["adversarial-audit", "leakage-audit", "benchmark-attack"],
    ),
}


def request(
    client: httpx.Client, method: str, path: str, payload: dict | None = None
) -> Any:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.state.exists():
        raise RuntimeError(
            "M13 credential state already exists; refusing to rotate it."
        )
    api_url = os.environ["SWARM_API_URL"].rstrip("/")
    operator_token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    signing_secret = os.environ["SWARM_PACKAGE_SIGNING_SECRET"]
    if len(signing_secret) < 32 or len(args.source_commit) != 40:
        raise RuntimeError(
            "Protected signing secret and full source commit are required."
        )
    headers = {"Authorization": f"Bearer {operator_token}"}
    state: dict[str, Any] = {"source_commit": args.source_commit, "roles": {}}
    with httpx.Client(base_url=api_url, headers=headers, timeout=30) as admin:
        existing_packages = request(admin, "GET", "/v1/packages")
        for key, (package_name, capabilities) in ROLES.items():
            registration = request(
                admin,
                "POST",
                "/v1/agents",
                {
                    "slug": f"vm1-{package_name}",
                    "display_name": package_name.replace("-", " ").title(),
                    "role": f"M13 {package_name} role",
                    "machine": "vm1-developer",
                    "hermes_profile": package_name,
                    "capabilities": capabilities,
                    "risk_ceiling": 1,
                },
            )
            manifest_path = ROOT / f"role-packages/{package_name}/manifest.yaml"
            package = load_role_package(manifest_path, ROOT / "workflows")
            document = canonical_manifest(package.manifest)
            manifest_digest = hashlib.sha256(document).hexdigest()
            existing = next(
                (
                    item
                    for item in existing_packages
                    if item["name"] == package_name and item["version"] == "1.0.0"
                ),
                None,
            )
            if existing is None:
                existing = request(
                    admin,
                    "POST",
                    "/v1/packages",
                    {
                        "manifest": package.manifest.model_dump(mode="json"),
                        "manifest_digest": manifest_digest,
                        "signature": hmac.new(
                            signing_secret.encode(), document, hashlib.sha256
                        ).hexdigest(),
                        "source_repository": "swarm-control-plane",
                        "source_commit": args.source_commit,
                        "created_by": "founder-operator",
                    },
                )
                existing_packages.append(existing)
            if existing["manifest_digest"] != manifest_digest:
                raise RuntimeError(f"Existing {package_name} package digest differs.")
            deployment = request(
                admin,
                "POST",
                "/v1/packages/deployments",
                {
                    "agent_id": registration["agent"]["id"],
                    "package_id": existing["id"],
                    "deployed_by": "founder-operator",
                },
            )
            state["roles"][key] = {
                "agent_id": registration["agent"]["id"],
                "slug": registration["agent"]["slug"],
                "token": registration["credential"]["token"],
                "package_id": existing["id"],
                "deployment_id": deployment["id"],
                "manifest_digest": manifest_digest,
            }
    descriptor = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                "state": str(args.state),
                "mode": oct(args.state.stat().st_mode & 0o777),
                "roles": {
                    key: {
                        field: value
                        for field, value in role.items()
                        if field != "token"
                    }
                    for key, role in state["roles"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
