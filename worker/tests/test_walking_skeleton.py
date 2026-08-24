from __future__ import annotations

import pytest

from swarm_worker.walking_skeleton import (
    verify_compensation_replay,
    verify_invalid_causality_fixture,
    verify_publication_replay,
)


def replay() -> dict:
    return {
        "id": "publication",
        "state": "complete",
        "bundle_digest": "a" * 64,
        "canonical_receipt": {
            "run_object_id": "run",
            "result_object_id": "result",
            "review_object_ids": ["review-a", "review-b"],
            "decision_object_id": "decision",
            "dossier_object_id": "dossier",
        },
        "projection_receipt": {"source_epoch": 1},
        "memory_receipt": {"disposition": "created"},
        "events": [
            {"sequence": 1, "event_type": "canonical_committed", "record_digest": "1"},
            {
                "sequence": 2,
                "event_type": "projections_confirmed",
                "record_digest": "2",
            },
            {"sequence": 3, "event_type": "memory_confirmed", "record_digest": "3"},
            {
                "sequence": 4,
                "event_type": "publication_completed",
                "record_digest": "4",
            },
        ],
    }


def test_complete_publication_replays_exactly() -> None:
    result = verify_publication_replay(replay())
    assert result["publication_state"] == "complete"
    assert len(result["canonical_object_ids"]) == 6


def test_invalid_causality_cannot_be_negative_or_accepted() -> None:
    result = verify_invalid_causality_fixture(
        {
            "outcome_kind": "invalid_attempt",
            "failure_mechanisms": ["forward join"],
            "labels": ["causality_rejected"],
        }
    )
    assert result["production_eligible"] is False
    with pytest.raises(ValueError, match="masquerade"):
        verify_invalid_causality_fixture(
            {
                "outcome_kind": "invalid_attempt",
                "failure_mechanisms": ["forward join"],
                "labels": ["valid_negative"],
            }
        )


def test_partial_publication_requires_failure_and_completion() -> None:
    result = verify_compensation_replay(
        [
            {"event_type": "canonical_committed"},
            {"event_type": "memory_failed"},
            {"event_type": "memory_confirmed"},
            {"event_type": "publication_completed"},
        ]
    )
    assert result["recovered"] is True
    with pytest.raises(ValueError, match="injected failure"):
        verify_compensation_replay([{"event_type": "publication_completed"}])
