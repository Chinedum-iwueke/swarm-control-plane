from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.models import OperationalNote
from app.schemas.operational_note import (
    OperationalNoteCreate,
    OperationalNoteTransition,
)
from app.services.operational_notes import note_digest, transition_note
from fastapi import HTTPException
from pydantic import ValidationError


def payload() -> OperationalNoteCreate:
    return OperationalNoteCreate(
        note_key="M14C-STORAGE-EFFICIENCY",
        subject="System-wide storage efficiency",
        finding="Bulletproof research memory is unexpectedly large for current usage.",
        evidence=["research.sqlite measured at approximately 27.7 GB"],
        affected_systems=["bulletproof_bt", "swarm-control-plane"],
        urgency="high",
        proposed_owner="vm1-operational-memory-steward",
        milestone_refs=["M14C"],
        repository_refs=["bulletproof_bt"],
        created_by="vm1-operational-memory-steward",
    )


def note() -> OperationalNote:
    document = payload()
    return OperationalNote(
        id=uuid4(),
        **document.model_dump(mode="python"),
        status="open",
        resolution_evidence=[],
        record_digest=note_digest(document),
    )


def test_note_digest_ignores_actor_but_binds_content() -> None:
    first = payload()
    second = first.model_copy(update={"created_by": "founder-operator"})
    assert note_digest(first) == note_digest(second)
    assert note_digest(first) != note_digest(
        first.model_copy(update={"finding": first.finding + " Audit required."})
    )


def test_unknown_fields_and_resolution_without_evidence_are_rejected() -> None:
    with pytest.raises(ValidationError):
        OperationalNoteCreate.model_validate(
            {**payload().model_dump(), "command": "rm"}
        )
    with pytest.raises(ValidationError, match="resolution evidence"):
        OperationalNoteTransition(
            action="resolve", actor="founder-operator", reason="Close without proof."
        )


def test_lifecycle_requires_audited_resolution_and_explicit_reopen() -> None:
    db = MagicMock()
    record = note()
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    transition_note(
        db,
        record,
        OperationalNoteTransition(
            action="assign",
            actor="founder-operator",
            reason="Assign a bounded storage audit.",
            assigned_to="vm1-engineering-worker",
        ),
        now=now,
    )
    assert record.status == "assigned"
    transition_note(
        db,
        record,
        OperationalNoteTransition(
            action="resolve",
            actor="founder-operator",
            reason="The approved audit and restore rehearsal completed.",
            evidence=["artifact:storage-audit-digest"],
        ),
        now=now + timedelta(minutes=1),
    )
    assert record.status == "resolved"
    assert record.resolution_evidence == ["artifact:storage-audit-digest"]
    with pytest.raises(HTTPException, match="reopened"):
        transition_note(
            db,
            record,
            OperationalNoteTransition(
                action="assign",
                actor="founder-operator",
                reason="Attempt reassignment without reopening.",
                assigned_to="vm1-engineering-worker",
            ),
        )
