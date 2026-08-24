"""WS-001 no-capital walking-skeleton replay verification."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

REQUIRED_CANONICAL_IDS = {
    "run_object_id",
    "result_object_id",
    "review_object_ids",
    "decision_object_id",
    "dossier_object_id",
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def invalid_run_envelope(run_id: uuid.UUID, run_payload: dict, fixture: dict) -> dict:
    return {
        "schema_version": "canonical-identity-v1.0.0",
        "object_schema_version": "canonical-evidence-v1.0.0",
        "object_id": str(run_id),
        "object_type": "run",
        "content_version": "1",
        "content_digest": digest(run_payload),
        "producer": {
            "system": "hermes-walking-skeleton",
            "native_type": "run",
            "native_id": str(run_id),
            "schema_version": fixture["schema_version"],
        },
        "aliases": [
            {
                "namespace": "hermes-walking-skeleton",
                "object_type": "run",
                "value": str(run_id),
            },
            {
                "namespace": "hermes-walking-skeleton",
                "object_type": "run",
                "value": f"invalid-causality:{run_id}",
            }
        ],
        "supersedes_object_id": None,
        "project": "bulletproof-bt",
        "access_class": "restricted",
        "authority_class": "operational",
        "payload": run_payload,
        "created_by": "ws001-pilot",
    }


def verify_publication_replay(replay: dict[str, Any]) -> dict[str, Any]:
    if replay.get("state") != "complete":
        raise ValueError("laboratory publication is not complete")
    receipt = replay.get("canonical_receipt") or {}
    missing = REQUIRED_CANONICAL_IDS - receipt.keys()
    if missing:
        raise ValueError(f"canonical receipt is incomplete: {sorted(missing)}")
    review_ids = receipt.get("review_object_ids") or []
    if len(review_ids) != 2 or len(set(review_ids)) != 2:
        raise ValueError("two distinct review objects are required")
    object_ids = [
        receipt["run_object_id"],
        receipt["result_object_id"],
        *review_ids,
        receipt["decision_object_id"],
        receipt["dossier_object_id"],
    ]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("canonical receipt aliases distinct lifecycle objects")
    if not replay.get("projection_receipt") or not replay.get("memory_receipt"):
        raise ValueError("projection and memory receipts are required")
    events = replay.get("events") or []
    sequences = [item.get("sequence") for item in events]
    if sequences != list(range(1, len(sequences) + 1)):
        raise ValueError("publication events are not contiguous")
    event_types = [str(item.get("event_type")) for item in events]
    for required in (
        "canonical_committed",
        "projections_confirmed",
        "memory_confirmed",
        "publication_completed",
    ):
        if required not in event_types:
            raise ValueError(f"publication event is missing: {required}")
    return {
        "publication_id": replay["id"],
        "publication_state": replay["state"],
        "bundle_digest": replay["bundle_digest"],
        "canonical_object_ids": object_ids,
        "event_count": len(events),
        "event_digest": digest(
            [
                {
                    "sequence": item["sequence"],
                    "event_type": item["event_type"],
                    "record_digest": item["record_digest"],
                }
                for item in events
            ]
        ),
    }


def verify_invalid_causality_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    if fixture.get("outcome_kind") != "invalid_attempt":
        raise ValueError("causality failure must be classified as invalid_attempt")
    mechanisms = fixture.get("failure_mechanisms") or []
    if not mechanisms:
        raise ValueError("invalid attempt requires a failure mechanism")
    forbidden = {"accepted", "valid_negative"}
    if forbidden.intersection(set(fixture.get("labels") or [])):
        raise ValueError("invalid attempt cannot masquerade as valid evidence")
    return {
        "classification": "invalid_attempt",
        "failure_mechanisms": mechanisms,
        "fixture_digest": digest(fixture),
        "production_eligible": False,
    }


def verify_compensation_replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    types = [str(item.get("event_type")) for item in events]
    failed = [name for name in types if name.endswith("_failed")]
    if not failed:
        raise ValueError("compensation replay must contain an injected failure")
    if types[-1] != "publication_completed":
        raise ValueError("compensation replay did not reach publication_completed")
    return {
        "injected_failures": failed,
        "recovered": True,
        "event_digest": digest(events),
    }
