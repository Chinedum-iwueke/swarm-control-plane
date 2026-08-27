#!/usr/bin/env python3
"""Exercise PLAT-002 identity, rotation, revocation, confused-deputy and secret boundaries."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx


def main() -> int:
    base = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token and os.environ.get("SWARM_ORCHESTRATOR_TOKEN_FILE"):
        token = Path(os.environ["SWARM_ORCHESTRATOR_TOKEN_FILE"]).read_text().strip()
    admin = httpx.Client(
        base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=90
    )
    overview = admin.get("/v1/workload-identities/overview").raise_for_status().json()
    identity = next(
        item for item in overview["identities"] if "task:lease" in item["scopes"]
    )
    rotation = (
        admin.post(
            f"/v1/workload-identities/{identity['id']}/credentials/rotate",
            json={"actor": "founder-operator", "overlap_seconds": 120},
        )
        .raise_for_status()
        .json()
    )
    scoped = httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {rotation['token']}"},
        timeout=30,
    )
    allowed = scoped.get("/v1/agent/me")
    denied_candidates = [
        ("fleet:write", "/v1/agent/fleet/observations"),
        ("research:write", "/v1/agent/research/briefs"),
        ("notes:write", "/v1/agent/operational-notes"),
    ]
    _, denied_path = next(
        item for item in denied_candidates if item[0] not in identity["scopes"]
    )
    denied = scoped.post(denied_path, json={})
    authorization = (
        admin.post(
            "/v1/workload-identities/authorize",
            json={
                "identity_id": identity["id"],
                "credential_prefix": rotation["token_prefix"],
                "action": "read-secret-reference",
                "required_scope": "secret:read",
                "context": {
                    "secret_value": "MUST-NOT-PERSIST",
                    "purpose": "PLAT-002 redaction drill",
                },
            },
        )
        .raise_for_status()
        .json()
    )
    emergency_denied = admin.post(
        "/v1/workload-identities/emergency-grants",
        json={
            "identity_id": identity["id"],
            "scopes": ["secret:read"],
            "reason": "PLAT-002 prohibited privilege expansion drill",
            "approved_by": "founder-operator",
            "independent_reviewer": "security-reviewer",
            "approval_reference": "PLAT-002-DRILL",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        },
    )
    rollback = (
        admin.post(
            f"/v1/workload-identities/{identity['id']}/credentials/rollback",
            json={"actor": "founder-operator"},
        )
        .raise_for_status()
        .json()
    )
    revoked = scoped.get("/v1/agent/me")
    report = {
        "schema_version": "plat002-pilot-v1.0.0",
        "identity_id": identity["id"],
        "manifest_digest": identity["manifest_digest"],
        "checks": {
            "enforcement_active": overview["enforcement_active"],
            "scoped_identity_allowed": allowed.status_code == 200,
            "confused_deputy_denied": denied.status_code in {403, 422},
            "secret_value_redacted": authorization["allowed"] is False,
            "privilege_expanding_break_glass_denied": emergency_denied.status_code
            == 422,
            "rotation_rollback_restored_prior": rollback["status"] == "rolled_back",
            "rolled_back_credential_revoked": revoked.status_code == 401,
        },
        "credential_prefixes": {"new": rotation["token_prefix"]},
        "capital_or_order_authority": False,
    }
    report["success"] = all(report["checks"].values())
    report["report_digest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path("/var/lib/invariance-swarm/plat002/report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
