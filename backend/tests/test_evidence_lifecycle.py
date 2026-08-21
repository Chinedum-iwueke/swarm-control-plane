from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.models.evidence import (
    CanonicalEvidenceObject,
    EvidenceDeletionRequest,
    EvidenceLifecycleState,
)
from app.schemas.lifecycle import (
    DeletionDecisionCreate,
    LifecycleActionCreate,
)
from app.services.evidence import EvidenceAccessContext
from app.services.lifecycle import (
    apply_lifecycle_action,
    decide_deletion,
    digest_document,
    is_active_expression,
)
from fastapi import HTTPException
from pydantic import ValidationError

NOW = datetime(2026, 8, 21, tzinfo=UTC)
ONE = UUID("11111111-1111-4111-8111-111111111111")
TWO = UUID("22222222-2222-4222-8222-222222222222")
ACCESS = EvidenceAccessContext(
    actor="knowledge-steward",
    projects=frozenset({"systematic-research"}),
    max_access_class="protected",
    may_write=True,
)


class Result:
    def __init__(self, values=()):
        self.values = list(values)

    def all(self):
        return self.values


def record(object_id: UUID, digest: str = "a" * 64, supersedes=None):
    return CanonicalEvidenceObject(
        id=object_id,
        schema_version="canonical-identity-v1.0.0",
        object_schema_version="canonical-evidence-v1.0.0",
        object_type="source",
        content_version="1",
        content_digest=digest,
        producer={},
        supersedes_object_id=supersedes,
        project="systematic-research",
        access_class="protected",
        authority_class="primary",
        payload={"kind": "source", "private": "payload"},
        created_by="knowledge-steward",
    )


def state(object_id: UUID, value: str = "active", hold: bool = False):
    return EvidenceLifecycleState(
        object_id=object_id,
        state=value,
        successor_object_id=None,
        retention_hold=hold,
        effective_at=NOW,
        version=1,
        updated_at=NOW,
    )


def fake_db(objects: dict, states: dict):
    db = MagicMock()

    def get(model, identity):
        if model is CanonicalEvidenceObject:
            return objects.get(identity)
        if model is EvidenceLifecycleState:
            return states.get(identity)
        if model is EvidenceDeletionRequest:
            return objects.get(identity)
        return None

    def add(item):
        if getattr(item, "id", None) is None:
            item.id = uuid4()

    db.get.side_effect = get
    db.add.side_effect = add
    db.scalars.return_value = Result()
    return db


def action(name: str, successor: UUID | None = None) -> LifecycleActionCreate:
    return LifecycleActionCreate(
        action=name,
        authority="knowledge-steward",
        reason="Verified lifecycle decision.",
        successor_object_id=successor,
        effective_at=NOW,
    )


def test_successor_actions_require_a_successor_and_shell_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="successor_object_id"):
        action("supersede")
    with pytest.raises(ValidationError, match="Extra inputs"):
        LifecycleActionCreate.model_validate(
            {**action("retract").model_dump(), "command": "delete everything"}
        )


def test_duplicate_consolidation_is_digest_bound_and_excludes_duplicate() -> None:
    old, canonical = record(ONE), record(TWO)
    old_state, canonical_state = state(ONE), state(TWO)
    db = fake_db({ONE: old, TWO: canonical}, {ONE: old_state, TWO: canonical_state})
    impact = SimpleNamespace(id=uuid4(), record_digest="b" * 64)
    with (
        patch("app.services.lifecycle.get_evidence_object", side_effect=[old, canonical]),
        patch("app.services.lifecycle._record_impact", return_value=impact),
    ):
        changed, event, _ = apply_lifecycle_action(
            db, ONE, action("consolidate", TWO), ACCESS
        )
    assert changed.state == "consolidated"
    assert changed.successor_object_id == TWO
    assert event.resulting_state == "consolidated"
    assert event.record_digest


def test_consolidation_rejects_nonidentical_content() -> None:
    old, canonical = record(ONE), record(TWO, "b" * 64)
    db = fake_db({ONE: old, TWO: canonical}, {ONE: state(ONE), TWO: state(TWO)})
    with (
        patch("app.services.lifecycle.get_evidence_object", side_effect=[old, canonical]),
        pytest.raises(HTTPException, match="identical content digests"),
    ):
        apply_lifecycle_action(db, ONE, action("consolidate", TWO), ACCESS)


def test_retraction_can_be_restored_but_terminal_state_cannot() -> None:
    item = record(ONE)
    item_state = state(ONE, "retracted")
    db = fake_db({ONE: item}, {ONE: item_state})
    impact = SimpleNamespace(id=uuid4(), record_digest="b" * 64)
    with (
        patch("app.services.lifecycle.get_evidence_object", return_value=item),
        patch("app.services.lifecycle._record_impact", return_value=impact),
    ):
        changed, _, _ = apply_lifecycle_action(db, ONE, action("restore"), ACCESS)
    assert changed.state == "active"

    item_state.state = "deleted"
    with (
        patch("app.services.lifecycle.get_evidence_object", return_value=item),
        pytest.raises(HTTPException, match="terminal"),
    ):
        apply_lifecycle_action(db, ONE, action("restore"), ACCESS)


def test_active_hold_and_same_authority_block_lawful_deletion() -> None:
    item = record(ONE)
    request = EvidenceDeletionRequest(
        id=TWO,
        object_id=ONE,
        status="pending",
        requested_by="privacy-authority",
        legal_basis="verified-erasure-request",
        reason="Authorized erasure.",
        payload_digest=digest_document(item.payload),
        record_digest="c" * 64,
    )
    db = fake_db({ONE: item, TWO: request}, {ONE: state(ONE, hold=True)})
    same = DeletionDecisionCreate(
        decision="approve",
        decided_by="privacy-authority",
        reason="Approved.",
    )
    with pytest.raises(HTTPException, match="independent"):
        decide_deletion(db, TWO, same, ACCESS)

    independent = same.model_copy(update={"decided_by": "security-authority"})
    with (
        patch("app.services.lifecycle.get_evidence_object", return_value=item),
        pytest.raises(HTTPException, match="retention hold"),
    ):
        decide_deletion(db, TWO, independent, ACCESS)


def test_lawful_deletion_scrubs_payload_and_preserves_digest_tombstone() -> None:
    item = record(ONE)
    original_content_digest = item.content_digest
    payload_digest = digest_document(item.payload)
    request = EvidenceDeletionRequest(
        id=TWO,
        object_id=ONE,
        status="pending",
        requested_by="privacy-authority",
        legal_basis="verified-erasure-request",
        reason="Authorized erasure.",
        payload_digest=payload_digest,
        record_digest="c" * 64,
    )
    item_state = state(ONE)
    db = fake_db({ONE: item, TWO: request}, {ONE: item_state})
    impact = SimpleNamespace(id=uuid4(), record_digest="d" * 64)
    decision = DeletionDecisionCreate(
        decision="approve",
        decided_by="security-authority",
        reason="Legal basis independently verified.",
    )
    with (
        patch("app.services.lifecycle.get_evidence_object", return_value=item),
        patch("app.services.lifecycle._record_impact", return_value=impact),
    ):
        decided, event, _ = decide_deletion(db, TWO, decision, ACCESS)
    assert decided.status == "approved"
    assert item_state.state == "deleted"
    assert item.payload["tombstone"] is True
    assert item.payload["original_payload_digest"] == payload_digest
    assert item.content_digest == original_content_digest
    assert event.legal_basis == "verified-erasure-request"


def test_inactive_filter_is_present_in_projection_queries() -> None:
    sql = str(is_active_expression().compile(compile_kwargs={"literal_binds": True}))
    assert "evidence_lifecycle_states" in sql
    assert "deleted" in sql


def test_lifecycle_state_serializes_derived_retrieval_eligibility() -> None:
    from app.schemas.lifecycle import LifecycleStateResponse

    active = LifecycleStateResponse.model_validate(state(ONE))
    inactive = LifecycleStateResponse.model_validate(state(TWO, "retracted"))
    assert active.active_for_retrieval is True
    assert inactive.active_for_retrieval is False


def test_migration_backfills_and_invalidates_projections() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/a4e7c9d21f60_add_evidence_lifecycle.py"
    ).read_text(encoding="utf-8")
    assert "INSERT INTO evidence_lifecycle_states" in migration
    assert "trg_evidence_lifecycle_states_freshness" in migration
    assert "uq_pending_evidence_deletion" in migration
