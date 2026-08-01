from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import OperationalNote, OperationalNoteEvent
from app.schemas.operational_note import (
    OperationalNoteCreate,
    OperationalNoteTransition,
)


def note_digest(payload: OperationalNoteCreate) -> str:
    document = payload.model_dump(mode="json", exclude={"created_by"})
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_note(db: Session, payload: OperationalNoteCreate) -> OperationalNote:
    digest = note_digest(payload)
    existing = db.scalar(
        select(OperationalNote).where(
            or_(
                OperationalNote.note_key == payload.note_key,
                OperationalNote.record_digest == digest,
            )
        )
    )
    if existing is not None:
        if existing.record_digest == digest:
            return existing
        raise HTTPException(
            status_code=409, detail="Operational note key already exists."
        )
    note = OperationalNote(
        **payload.model_dump(mode="python"),
        status="open",
        resolution_evidence=[],
        record_digest=digest,
    )
    db.add(note)
    db.flush()
    db.add(
        OperationalNoteEvent(
            note_id=note.id,
            event_type="created",
            previous_status=None,
            new_status="open",
            actor=payload.created_by,
            reason="Operational observation recorded immutably.",
            evidence=payload.evidence,
        )
    )
    return note


def transition_note(
    db: Session,
    note: OperationalNote,
    payload: OperationalNoteTransition,
    *,
    now: datetime | None = None,
) -> OperationalNote:
    previous = note.status
    targets = {
        "assign": "assigned",
        "defer": "deferred",
        "resolve": "resolved",
        "reopen": "open",
    }
    target = targets[payload.action]
    if previous == target:
        raise HTTPException(status_code=409, detail=f"Note is already {target}.")
    if previous == "resolved" and payload.action != "reopen":
        raise HTTPException(
            status_code=409, detail="Resolved note must be reopened first."
        )
    if payload.action == "reopen" and previous != "resolved":
        raise HTTPException(
            status_code=409, detail="Only resolved notes may be reopened."
        )
    timestamp = now or datetime.now(UTC)
    note.status = target
    note.updated_at = timestamp
    if payload.action == "assign":
        note.assigned_to = payload.assigned_to
        note.deferred_until = None
        note.deferral_reason = None
    elif payload.action == "defer":
        if payload.deferred_until is None or payload.deferred_until <= timestamp:
            raise HTTPException(
                status_code=422, detail="Deferral must end in the future."
            )
        note.deferred_until = payload.deferred_until
        note.deferral_reason = payload.reason
    elif payload.action == "resolve":
        note.resolution_evidence = payload.evidence
    elif payload.action == "reopen":
        note.resolution_evidence = []
        note.deferred_until = None
        note.deferral_reason = None
    db.add(
        OperationalNoteEvent(
            note_id=note.id,
            event_type=payload.action,
            previous_status=previous,
            new_status=target,
            actor=payload.actor,
            reason=payload.reason,
            evidence=payload.evidence,
        )
    )
    db.flush()
    return note
