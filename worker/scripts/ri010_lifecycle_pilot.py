#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

TIMEOUT_SECONDS = 3600.0
PROJECT = "systematic-research"
IDS = {
    "canonical": UUID("10a00000-0000-4000-8000-000000000001"),
    "duplicate": UUID("10a00000-0000-4000-8000-000000000002"),
    "prior": UUID("10a00000-0000-4000-8000-000000000003"),
    "corrected": UUID("10a00000-0000-4000-8000-000000000004"),
    "deletion": UUID("10a00000-0000-4000-8000-000000000005"),
}


def digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def request(
    client: httpx.Client,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    accepted: tuple[int, ...] = (200, 201),
) -> dict[str, Any]:
    response = client.request(method, path, json=payload)
    if response.status_code not in accepted:
        response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise TypeError(f"{path} did not return an object")
    return value


def source_payload(title: str) -> dict[str, Any]:
    return {
        "kind": "source",
        "title": title,
        "origin": "fixture://ri-010",
        "rights": "synthetic lifecycle pilot",
        "acquired_at": "2026-08-21T00:00:00Z",
    }


def register(
    client: httpx.Client,
    key: str,
    title: str,
    *,
    supersedes: UUID | None = None,
    content_version: str = "1",
) -> dict[str, Any]:
    body = source_payload(title)
    object_id = IDS[key]
    native_id = f"ri010-{key}"
    return request(
        client,
        "POST",
        "/v1/research/evidence/objects",
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": str(object_id),
            "object_type": "source",
            "content_version": content_version,
            "content_digest": digest(body),
            "producer": {
                "system": "hermes",
                "native_type": "source",
                "native_id": native_id,
                "schema_version": "ri010-pilot-v1",
            },
            "aliases": [
                {"namespace": "hermes", "object_type": "source", "value": native_id}
            ],
            "supersedes_object_id": str(supersedes) if supersedes else None,
            "project": PROJECT,
            "access_class": "protected",
            "authority_class": "primary",
            "payload": body,
            "created_by": "knowledge-steward",
        },
    )


def rebuild_if_stale(client: httpx.Client, namespace: str) -> dict[str, Any]:
    status_path = f"/v1/research/{namespace}/projections/status"
    rebuild_path = f"/v1/research/{namespace}/projections/rebuild"
    response = client.get(status_path)
    stale = response.status_code == 409 or response.json().get("stale", False)
    if stale:
        result = request(client, "POST", rebuild_path, {})
        return {"rebuilt": True, "result": result}
    response.raise_for_status()
    return {"rebuilt": False, "result": response.json()}


def main() -> int:
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN", "")
    if not api_url or len(token) < 20:
        print("SWARM_API_URL and SWARM_ORCHESTRATOR_TOKEN are required.", file=sys.stderr)
        return 2
    now = datetime.now(UTC).isoformat()
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT_SECONDS,
    ) as client:
        canonical = register(client, "canonical", "RI-010 duplicate fixture")
        duplicate = register(client, "duplicate", "RI-010 duplicate fixture")
        consolidated = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['duplicate']}/actions",
            {
                "action": "consolidate",
                "authority": "knowledge-steward",
                "reason": "Verified duplicate canonical content.",
                "successor_object_id": str(IDS["canonical"]),
                "effective_at": now,
            },
        )
        prior = register(client, "prior", "RI-010 prior edition")
        corrected = register(
            client,
            "corrected",
            "RI-010 corrected edition",
            supersedes=IDS["prior"],
            content_version="2",
        )
        superseded = request(
            client,
            "GET",
            f"/v1/research/evidence/lifecycle/objects/{IDS['prior']}",
        )
        retracted = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['canonical']}/actions",
            {
                "action": "retract",
                "authority": "knowledge-steward",
                "reason": "Synthetic retraction recovery fixture.",
                "successor_object_id": None,
                "effective_at": now,
            },
        )
        restored = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['canonical']}/actions",
            {
                "action": "restore",
                "authority": "independent-evaluator",
                "reason": "Synthetic source validity restored after replay.",
                "successor_object_id": None,
                "effective_at": now,
            },
        )
        deletion = register(client, "deletion", "RI-010 protected deletion fixture")
        held = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['deletion']}/retention-hold",
            {"authority": "privacy-authority", "reason": "Verify hold enforcement.", "active": True},
        )
        deletion_request = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['deletion']}/deletion-requests",
            {
                "requested_by": "privacy-authority",
                "legal_basis": "synthetic-ri010-erasure-fixture",
                "reason": "Exercise independent lawful deletion workflow.",
            },
        )
        blocked = client.post(
            f"/v1/research/evidence/lifecycle/deletion-requests/{deletion_request['id']}/decision",
            json={
                "decision": "approve",
                "decided_by": "security-authority",
                "reason": "Independent synthetic approval.",
            },
        )
        if blocked.status_code != 409:
            raise RuntimeError("Active retention hold did not block deletion")
        request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{IDS['deletion']}/retention-hold",
            {"authority": "privacy-authority", "reason": "Hold fixture completed.", "active": False},
        )
        deleted_request = request(
            client,
            "POST",
            f"/v1/research/evidence/lifecycle/deletion-requests/{deletion_request['id']}/decision",
            {
                "decision": "approve",
                "decided_by": "security-authority",
                "reason": "Independent legal basis verification passed.",
            },
        )
        deleted = request(
            client,
            "GET",
            f"/v1/research/evidence/lifecycle/objects/{IDS['deletion']}",
        )
        projections = {
            "retrieval": rebuild_if_stale(client, "retrieval"),
            "graph": rebuild_if_stale(client, "graph"),
        }
    result = {
        "objects": {
            "canonical": canonical["object_id"],
            "duplicate": duplicate["object_id"],
            "prior": prior["object_id"],
            "corrected": corrected["object_id"],
            "deletion": deletion["object_id"],
        },
        "checks": {
            "duplicate_consolidated": consolidated["state"]["state"] == "consolidated",
            "supersession_propagated": superseded["state"]["state"] == "superseded",
            "retraction_recorded": retracted["state"]["state"] == "retracted",
            "restore_reactivated": restored["state"]["state"] == "active",
            "retention_hold_blocked_deletion": blocked.status_code == 409,
            "lawful_deletion_terminal": deleted["state"]["state"] == "deleted",
            "independent_deletion_approved": deleted_request["decided_by"] == "security-authority",
            "projections_current": all(item["result"].get("stale") is not True for item in projections.values()),
        },
        "dossier_digests": {
            "consolidation": consolidated["dossier_digest"],
            "supersession": superseded["dossier_digest"],
            "retraction": retracted["dossier_digest"],
            "restore": restored["dossier_digest"],
            "retention": held["dossier_digest"],
            "deletion": deleted["dossier_digest"],
        },
        "projections": projections,
    }
    if not all(result["checks"].values()):
        raise RuntimeError("RI-010 pilot checks did not all pass")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
