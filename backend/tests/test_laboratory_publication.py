from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from app.schemas.laboratory import (
    LaboratoryPublicationCreate,
    MemoryReceiptCreate,
    ProjectionReceiptCreate,
    PublicationFailureCreate,
)


def test_canonical_result_object_is_allowed_by_head_migration() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/f1a6d3c84b20_allow_canonical_result_objects.py"
    ).read_text(encoding="utf-8")
    assert "'run','result','review'" in migration
from app.services.laboratory import (
    create_publication,
    digest_document,
    record_failure,
    record_memory_receipt,
    record_projection_receipt,
)
from fastapi import HTTPException

TRIAL_ID = UUID("10000000-0000-4000-8000-000000000001")
RESULT_ID = UUID("10000000-0000-4000-8000-000000000002")
RUN_ID = UUID("10000000-0000-4000-8000-000000000003")
PUBLICATION_ID = UUID("10000000-0000-4000-8000-000000000004")
DIGEST = "a" * 64


def publication_payload(**updates) -> LaboratoryPublicationCreate:
    document = {
        "schema_version": "laboratory-publication-v1.0.0",
        "trial_id": str(TRIAL_ID),
        "result_id": str(RESULT_ID),
        "run_object_id": str(RUN_ID),
        "repository_commit": "b" * 40,
        "dataset_digest": "c" * 64,
        "market_model_bundle_digest": "d" * 64,
        "representation_contract_digest": "e" * 64,
        "bundle_digest": "f" * 64,
        "bundle_manifest_digest": "1" * 64,
    }
    document.update(updates)
    document["request_digest"] = digest_document(document)
    return LaboratoryPublicationCreate.model_validate(document)


def test_publication_request_is_digest_bound() -> None:
    payload = publication_payload().model_copy(update={"request_digest": "0" * 64})
    with pytest.raises(HTTPException, match="request digest mismatch"):
        create_publication(MagicMock(), payload)


def test_unknown_or_unreviewed_lineage_is_not_publishable() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with (
        patch(
            "app.services.laboratory._load_registry_lineage",
            side_effect=HTTPException(
                409, "Two independent reviews and a decision are required."
            ),
        ),
        pytest.raises(HTTPException, match="Two independent reviews"),
    ):
        create_publication(db, publication_payload())


def test_publication_commits_negative_result_and_dossier_once() -> None:
    payload = publication_payload()
    trial = SimpleNamespace(
        id=TRIAL_ID,
        plan={"dataset_digest": "c" * 64, "engine_digest": "2" * 64},
    )
    result = SimpleNamespace(
        id=RESULT_ID,
        outcome="rejected",
        result={"metrics": {"oos_sharpe": -0.3}},
    )
    experiment = SimpleNamespace(manifest={"repository_commit": "b" * 40})
    run = SimpleNamespace(
        id=RUN_ID,
        payload={
            "bundle_digest": "f" * 64,
            "bundle_manifest_digest": "1" * 64,
            "code_digest": "2" * 64,
            "market_model_bundle_digest": "d" * 64,
            "representation_contract_digest": "e" * 64,
        },
    )
    reviews = [
        SimpleNamespace(
            id=UUID("20000000-0000-4000-8000-000000000001"),
            reviewer="statistical-reviewer",
            verdict="approved",
            review={"summary": "Reproduced."},
        ),
        SimpleNamespace(
            id=UUID("20000000-0000-4000-8000-000000000002"),
            reviewer="adversarial-reviewer",
            verdict="rejected",
            review={"summary": "Negative result retained."},
        ),
    ]
    decision = SimpleNamespace(
        id=UUID("30000000-0000-4000-8000-000000000001"),
        decided_by="senior-researcher",
        decision="reject",
        rationale="The locked gate failed.",
        decided_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    objects = [
        SimpleNamespace(
            id=UUID(f"40000000-0000-4000-8000-00000000000{index}"),
            content_digest=DIGEST,
        )
        for index in range(1, 6)
    ]
    db = MagicMock()
    db.scalar.side_effect = [None, None, 0]
    with (
        patch(
            "app.services.laboratory._load_registry_lineage",
            return_value=(trial, result, experiment, run, reviews, decision),
        ),
        patch("app.services.laboratory._register", side_effect=objects) as register,
    ):
        publication = create_publication(db, payload)
    assert publication.state == "awaiting_projections"
    assert publication.canonical_receipt["result_object_id"] == str(objects[0].id)
    assert register.call_args_list[0].kwargs["payload"]["outcome"] == "negative"
    assert register.call_args_list[-1].kwargs["native_type"] == "episode"
    db.commit.assert_called_once()


def test_projection_receipt_must_match_current_projection() -> None:
    publication = SimpleNamespace(
        id=PUBLICATION_ID,
        projection_receipt={},
        failure={},
        state="awaiting_projections",
    )
    graph = SimpleNamespace(manifest_digest="a" * 64, source_epoch=8)
    retrieval = SimpleNamespace(corpus_digest="b" * 64, source_epoch=8)
    db = MagicMock()
    db.scalar.side_effect = [publication, 0]
    db.get.side_effect = [graph, retrieval]
    receipt = ProjectionReceiptCreate(
        schema_version="laboratory-projection-receipt-v1.0.0",
        graph_manifest_digest="a" * 64,
        graph_source_epoch=8,
        retrieval_corpus_digest="b" * 64,
        retrieval_source_epoch=8,
    )
    assert (
        record_projection_receipt(db, PUBLICATION_ID, receipt).state
        == "awaiting_memory"
    )


def test_memory_publication_is_ordered_and_digest_bound() -> None:
    publication = SimpleNamespace(
        id=PUBLICATION_ID,
        projection_receipt={"confirmed": True},
        memory_receipt={},
        failure={},
        state="awaiting_memory",
        bundle_digest="f" * 64,
        completed_at=None,
    )
    db = MagicMock()
    db.scalar.side_effect = [publication, 0, 1]
    receipt = MemoryReceiptCreate(
        schema_version="bulletproof-memory-publication-receipt-v1.0.0",
        bundle_digest="f" * 64,
        memory_database_digest="9" * 64,
        publication_key="bt008-test",
        disposition="created",
    )
    assert record_memory_receipt(db, PUBLICATION_ID, receipt).state == "complete"
    assert publication.completed_at is not None


def test_partial_failure_remains_retryable_without_deleting_canonical_receipt() -> None:
    publication = SimpleNamespace(
        id=PUBLICATION_ID,
        state="awaiting_memory",
        failure={},
        canonical_receipt={"result_object_id": str(RESULT_ID)},
    )
    db = MagicMock()
    db.scalar.side_effect = [publication, 0]
    failure = PublicationFailureCreate(
        stage="memory",
        category="temporary_unavailable",
        detail="Memory database is locked.",
        retryable=True,
    )
    result = record_failure(db, PUBLICATION_ID, failure)
    assert result.state == "memory_failed"
    assert result.canonical_receipt["result_object_id"] == str(RESULT_ID)
