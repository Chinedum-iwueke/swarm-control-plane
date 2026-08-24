#!/usr/bin/env python3
"""Verify the live BT-009 publication as the WS-001 no-capital skeleton."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

import httpx

from swarm_worker.walking_skeleton import (
    digest,
    invalid_run_envelope,
    invalid_run_payload,
    verify_compensation_replay,
    verify_invalid_causality_fixture,
    verify_publication_replay,
)

NAMESPACE = uuid.UUID("0bf94fc0-1cdb-4c68-8f0f-47874a0b8071")


def register_invalid_fixture(client: httpx.Client, replay: dict, fixture: dict) -> dict:
    source_run = client.get(f"/v1/research/evidence/objects/{replay['run_object_id']}")
    source_run.raise_for_status()
    dataset_ids = source_run.json()["payload"]["dataset_object_ids"]
    run_payload = invalid_run_payload(dataset_ids, fixture)
    run_id = uuid.uuid5(NAMESPACE, f"invalid-run:{digest(fixture)}")
    envelope = invalid_run_envelope(run_id, run_payload, fixture)
    registered = client.post("/v1/research/evidence/objects", json=envelope)
    if registered.is_error:
        raise RuntimeError(
            "Canonical invalid-fixture registration failed "
            f"with HTTP {registered.status_code}: {registered.text[:2000]}"
        )
    outcome_payload = {
        "project": "bulletproof-bt",
        "evidence_object_id": str(run_id),
        "outcome_kind": "invalid_attempt",
        "question": fixture["question"],
        "scope": {
            "population": "deterministic BTC fixture",
            "horizon": "one signal interval",
            "environment": "WS-001 no-capital causality fixture",
            "limitations": ["deliberately invalid; no performance inference"],
        },
        "method": "Inject a forward auxiliary join and require the causal gate to reject it.",
        "uncertainty": [
            {
                "source": "implementation",
                "representation": "unknown",
                "detail": "No scientific estimate is valid after the causality failure.",
            }
        ],
        "failure_mechanisms": fixture["failure_mechanisms"],
        "affected_claim_ids": [],
        "recorded_by": "ws001-pilot",
    }
    outcome = client.post("/v1/research/memory/outcomes", json=outcome_payload)
    if outcome.status_code == 409:
        search = client.get(
            "/v1/research/memory/outcomes/search",
            params={"query": "forward auxiliary join", "project": "bulletproof-bt"},
        )
        search.raise_for_status()
        matches = [
            item
            for item in search.json()["invalid_attempt"]
            if item["evidence_object_id"] == str(run_id)
        ]
        if len(matches) != 1:
            outcome.raise_for_status()
        return {"run_object_id": str(run_id), "outcome": matches[0]}
    outcome.raise_for_status()
    return {"run_object_id": str(run_id), "outcome": outcome.json()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    ) as client:
        response = client.get(
            f"/v1/research/laboratory/publications/{args.publication_id}/replay"
        )
        response.raise_for_status()
        replay = response.json()

    valid_negative = verify_publication_replay(replay)
    invalid_fixture = {
        "schema_version": "ws001-invalid-causality-v1.0.0",
        "outcome_kind": "invalid_attempt",
        "question": "Does a deliberately forward-joined signal predict its source return?",
        "failure_mechanisms": [
            "forward auxiliary join violates point-in-time causality"
        ],
        "labels": ["causality_rejected", "retained_failure"],
        "source_publication_id": args.publication_id,
    }
    invalid_causality = verify_invalid_causality_fixture(invalid_fixture)
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    ) as client:
        invalid_causality.update(
            register_invalid_fixture(client, replay, invalid_fixture)
        )
    compensation_events = [
        {"sequence": 1, "event_type": "canonical_committed"},
        {"sequence": 2, "event_type": "memory_failed"},
        {"sequence": 3, "event_type": "projections_confirmed"},
        {"sequence": 4, "event_type": "memory_confirmed"},
        {"sequence": 5, "event_type": "publication_completed"},
    ]
    compensation = verify_compensation_replay(compensation_events)
    report = {
        "schema_version": "ws001-walking-skeleton-report-v1.0.0",
        "success": True,
        "capital_or_order_authority": False,
        "valid_negative_path": valid_negative,
        "invalid_causality_path": invalid_causality,
        "partial_publication_compensation": compensation,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
