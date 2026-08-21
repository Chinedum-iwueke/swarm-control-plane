from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.evidence import (
    CanonicalEvidenceAuditEvent,
    CanonicalEvidenceEdge,
    CanonicalEvidenceObject,
    EvidenceConsolidationReceipt,
    EvidenceDeletionRequest,
    EvidenceLifecycleEvent,
    EvidenceLifecycleImpactReport,
    EvidenceLifecycleState,
)
from app.models.memory import EvidenceDossier
from app.schemas.lifecycle import (
    DeletionDecisionCreate,
    DeletionRequestCreate,
    LifecycleActionCreate,
    RetentionHoldCreate,
)
from app.services.evidence import EvidenceAccessContext, get_evidence_object

INACTIVE_STATES = frozenset({"consolidated", "superseded", "retracted", "expired", "deleted"})
TERMINAL_STATES = frozenset({"consolidated", "superseded", "deleted"})


def digest_document(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def lifecycle_state(db: Session, object_id: UUID) -> EvidenceLifecycleState | None:
    return db.get(EvidenceLifecycleState, object_id)


def is_active_expression():
    return ~CanonicalEvidenceObject.id.in_(
        select(EvidenceLifecycleState.object_id).where(
            EvidenceLifecycleState.state.in_(INACTIVE_STATES)
        )
    )


def ensure_lifecycle_state(
    db: Session, object_id: UUID, *, effective_at: datetime | None = None
) -> EvidenceLifecycleState:
    state = db.get(EvidenceLifecycleState, object_id)
    if state is not None:
        return state
    now = effective_at or datetime.now(UTC)
    state = EvidenceLifecycleState(
        object_id=object_id,
        state="active",
        retention_hold=False,
        effective_at=now,
        version=1,
        updated_at=now,
    )
    db.add(state)
    db.flush()
    return state


def register_declared_supersession(
    db: Session,
    previous: CanonicalEvidenceObject,
    successor: CanonicalEvidenceObject,
    authority: str,
) -> None:
    successor_state = ensure_lifecycle_state(db, successor.id)
    previous_state = ensure_lifecycle_state(db, previous.id)
    if previous_state.state != "active":
        raise HTTPException(status_code=409, detail="Superseded evidence is not active.")
    event = _record_event(
        db,
        previous,
        previous_state,
        event_type="supersede",
        resulting_state="superseded",
        authority=authority,
        reason="Canonical successor registered.",
        effective_at=datetime.now(UTC),
        successor_object_id=successor.id,
        detail={"registration_propagated": True},
    )
    _record_impact(db, previous.id, event)
    if successor_state.state != "active":
        raise HTTPException(status_code=409, detail="Registered successor is not active.")


def apply_lifecycle_action(
    db: Session,
    object_id: UUID,
    payload: LifecycleActionCreate,
    access: EvidenceAccessContext,
) -> tuple[EvidenceLifecycleState, EvidenceLifecycleEvent, EvidenceLifecycleImpactReport]:
    record = get_evidence_object(db, object_id, access, audit=False)
    state = ensure_lifecycle_state(db, object_id)
    if payload.effective_at > datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Lifecycle action cannot take effect in the future.")
    if state.state == "deleted":
        raise HTTPException(status_code=409, detail="Deleted evidence is terminal.")

    resulting_state = {
        "consolidate": "consolidated",
        "supersede": "superseded",
        "correct": "superseded",
        "retract": "retracted",
        "expire": "expired",
        "decay": "expired",
        "restore": "active",
    }[payload.action]
    if payload.action == "restore":
        if state.state not in {"retracted", "expired"}:
            raise HTTPException(status_code=409, detail="Only retracted or expired evidence may be restored.")
    elif state.state != "active":
        raise HTTPException(status_code=409, detail="Only active evidence may transition.")

    successor = None
    if payload.successor_object_id is not None:
        successor = get_evidence_object(db, payload.successor_object_id, access, audit=False)
        if successor.id == record.id:
            raise HTTPException(status_code=422, detail="Evidence cannot replace itself.")
        if successor.project != record.project or successor.object_type != record.object_type:
            raise HTTPException(status_code=422, detail="Successor identity is incompatible.")
        successor_state = ensure_lifecycle_state(db, successor.id)
        if successor_state.state != "active":
            raise HTTPException(status_code=409, detail="Successor evidence is not active.")
        if payload.action == "consolidate" and successor.content_digest != record.content_digest:
            raise HTTPException(status_code=422, detail="Consolidation requires identical content digests.")
        if payload.action in {"supersede", "correct"} and successor.supersedes_object_id != record.id:
            raise HTTPException(status_code=422, detail="Successor does not declare the replaced object.")

    event = _record_event(
        db,
        record,
        state,
        event_type=payload.action,
        resulting_state=resulting_state,
        authority=payload.authority,
        reason=payload.reason,
        effective_at=payload.effective_at,
        successor_object_id=payload.successor_object_id,
        detail={"correction": payload.action == "correct"},
    )
    if payload.action == "consolidate":
        material = {
            "canonical_object_id": str(successor.id),
            "duplicate_object_id": str(record.id),
            "authority": payload.authority,
            "reason": payload.reason,
            "event_id": str(event.id),
        }
        db.add(
            EvidenceConsolidationReceipt(
                canonical_object_id=successor.id,
                duplicate_object_id=record.id,
                authority=payload.authority,
                reason=payload.reason,
                record_digest=digest_document(material),
            )
        )
    impact = _record_impact(db, record.id, event)
    db.commit()
    db.refresh(state)
    db.refresh(event)
    db.refresh(impact)
    return state, event, impact


def set_retention_hold(
    db: Session,
    object_id: UUID,
    payload: RetentionHoldCreate,
    access: EvidenceAccessContext,
) -> tuple[EvidenceLifecycleState, EvidenceLifecycleEvent, EvidenceLifecycleImpactReport]:
    record = get_evidence_object(db, object_id, access, audit=False)
    state = ensure_lifecycle_state(db, object_id)
    if state.state == "deleted":
        raise HTTPException(status_code=409, detail="Deleted evidence is terminal.")
    if state.retention_hold == payload.active:
        raise HTTPException(status_code=409, detail="Retention hold already has the requested state.")
    event_type = "hold_placed" if payload.active else "hold_released"
    prior = state.state
    state.retention_hold = payload.active
    state.hold_authority = payload.authority if payload.active else None
    state.hold_reason = payload.reason if payload.active else None
    state.version += 1
    state.updated_at = datetime.now(UTC)
    event = _new_event(
        record,
        event_type=event_type,
        prior_state=prior,
        resulting_state=prior,
        authority=payload.authority,
        reason=payload.reason,
        effective_at=state.updated_at,
        successor_object_id=state.successor_object_id,
        detail={"retention_hold": payload.active},
    )
    db.add(event)
    db.flush()
    impact = _record_impact(db, record.id, event)
    db.commit()
    return state, event, impact


def request_deletion(
    db: Session,
    object_id: UUID,
    payload: DeletionRequestCreate,
    access: EvidenceAccessContext,
) -> EvidenceDeletionRequest:
    record = get_evidence_object(db, object_id, access, audit=False)
    state = ensure_lifecycle_state(db, object_id)
    if state.state == "deleted":
        raise HTTPException(status_code=409, detail="Evidence is already deleted.")
    pending = db.scalar(
        select(EvidenceDeletionRequest).where(
            EvidenceDeletionRequest.object_id == object_id,
            EvidenceDeletionRequest.status == "pending",
        )
    )
    if pending is not None:
        return pending
    material = {
        "object_id": str(object_id),
        "requested_by": payload.requested_by,
        "legal_basis": payload.legal_basis,
        "reason": payload.reason,
        "payload_digest": digest_document(record.payload),
    }
    request = EvidenceDeletionRequest(
        object_id=object_id,
        status="pending",
        requested_by=payload.requested_by,
        legal_basis=payload.legal_basis,
        reason=payload.reason,
        payload_digest=material["payload_digest"],
        record_digest=digest_document(material),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def decide_deletion(
    db: Session,
    request_id: UUID,
    payload: DeletionDecisionCreate,
    access: EvidenceAccessContext,
) -> tuple[EvidenceDeletionRequest, EvidenceLifecycleEvent | None, EvidenceLifecycleImpactReport | None]:
    request = db.get(EvidenceDeletionRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Deletion request not found.")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Deletion request is already decided.")
    if request.requested_by == payload.decided_by:
        raise HTTPException(status_code=422, detail="Deletion requires an independent approving authority.")
    record = get_evidence_object(db, request.object_id, access, audit=False)
    state = ensure_lifecycle_state(db, record.id)
    now = datetime.now(UTC)
    request.decided_by = payload.decided_by
    request.decision_reason = payload.reason
    request.decided_at = now
    if payload.decision == "reject":
        request.status = "rejected"
        db.commit()
        return request, None, None
    if state.retention_hold:
        raise HTTPException(status_code=409, detail="Active retention hold blocks lawful deletion.")
    request.status = "approved"
    event = _record_event(
        db,
        record,
        state,
        event_type="lawful_delete",
        resulting_state="deleted",
        authority=payload.decided_by,
        legal_basis=request.legal_basis,
        reason=payload.reason,
        effective_at=now,
        detail={"deletion_request_id": str(request.id), "payload_digest": request.payload_digest},
    )
    record.payload = {
        "kind": record.object_type,
        "tombstone": True,
        "deletion_request_id": str(request.id),
        "original_payload_digest": request.payload_digest,
    }
    db.add(
        CanonicalEvidenceAuditEvent(
            object_id=record.id,
            event_type="payload_deleted",
            actor=payload.decided_by,
            detail="Protected payload lawfully deleted; identity, digest, and lineage retained.",
        )
    )
    impact = _record_impact(db, record.id, event)
    db.commit()
    return request, event, impact


def lifecycle_dossier(db: Session, object_id: UUID, access: EvidenceAccessContext) -> dict[str, Any]:
    get_evidence_object(db, object_id, access, audit=False)
    state = ensure_lifecycle_state(db, object_id)
    events = list(
        db.scalars(
            select(EvidenceLifecycleEvent)
            .where(EvidenceLifecycleEvent.object_id == object_id)
            .order_by(EvidenceLifecycleEvent.created_at, EvidenceLifecycleEvent.id)
        ).all()
    )
    event_ids = [event.id for event in events]
    impacts = list(
        db.scalars(
            select(EvidenceLifecycleImpactReport)
            .where(EvidenceLifecycleImpactReport.event_id.in_(event_ids))
            .order_by(EvidenceLifecycleImpactReport.created_at)
        ).all()
    ) if event_ids else []
    material = {
        "object_id": str(object_id),
        "state": state.state,
        "version": state.version,
        "events": [event.record_digest for event in events],
        "impacts": [impact.record_digest for impact in impacts],
    }
    db.commit()
    return {"state": state, "events": events, "impacts": impacts, "dossier_digest": digest_document(material)}


def list_lifecycle_states(
    db: Session,
    access: EvidenceAccessContext,
    *,
    include_active: bool = False,
    limit: int = 100,
) -> list[EvidenceLifecycleState]:
    statement = select(EvidenceLifecycleState).join(
        CanonicalEvidenceObject,
        CanonicalEvidenceObject.id == EvidenceLifecycleState.object_id,
    )
    if "*" not in access.projects:
        statement = statement.where(CanonicalEvidenceObject.project.in_(access.projects))
    if not include_active:
        statement = statement.where(EvidenceLifecycleState.state != "active")
    return list(
        db.scalars(
            statement.order_by(EvidenceLifecycleState.updated_at.desc()).limit(limit)
        ).all()
    )


def _record_event(
    db: Session,
    record: CanonicalEvidenceObject,
    state: EvidenceLifecycleState,
    *,
    event_type: str,
    resulting_state: str,
    authority: str,
    reason: str,
    effective_at: datetime,
    successor_object_id: UUID | None = None,
    legal_basis: str | None = None,
    detail: dict[str, Any] | None = None,
) -> EvidenceLifecycleEvent:
    prior_state = state.state
    state.state = resulting_state
    state.successor_object_id = successor_object_id
    state.effective_at = effective_at
    state.version += 1
    state.updated_at = datetime.now(UTC)
    event = _new_event(
        record,
        event_type=event_type,
        prior_state=prior_state,
        resulting_state=resulting_state,
        authority=authority,
        reason=reason,
        effective_at=effective_at,
        successor_object_id=successor_object_id,
        legal_basis=legal_basis,
        detail=detail or {},
    )
    db.add(event)
    db.flush()
    return event


def _new_event(record: CanonicalEvidenceObject, **values: Any) -> EvidenceLifecycleEvent:
    material = {"object_id": str(record.id), **values}
    material["successor_object_id"] = str(values.get("successor_object_id")) if values.get("successor_object_id") else None
    return EvidenceLifecycleEvent(
        object_id=record.id,
        record_digest=digest_document(material),
        **values,
    )


def _record_impact(
    db: Session, object_id: UUID, event: EvidenceLifecycleEvent
) -> EvidenceLifecycleImpactReport:
    edge_count = len(
        list(
            db.scalars(
                select(CanonicalEvidenceEdge.id).where(
                    or_(
                        CanonicalEvidenceEdge.subject_id == object_id,
                        CanonicalEvidenceEdge.object_id == object_id,
                        CanonicalEvidenceEdge.provenance_object_id == object_id,
                    )
                )
            ).all()
        )
    )
    dossier_ids: list[str] = []
    for dossier in db.scalars(select(EvidenceDossier)).all():
        snapshots = dossier.dossier.get("objects", {})
        if any(
            any(item.get("object_id") == str(object_id) for item in group)
            for group in snapshots.values()
        ):
            dossier_ids.append(str(dossier.id))
    dependent_ids = list(
        db.scalars(
            select(CanonicalEvidenceEdge.subject_id).where(
                CanonicalEvidenceEdge.object_id == object_id
            )
        ).all()
    )
    impact = {
        "active_retrieval_excluded": event.resulting_state in INACTIVE_STATES,
        "projection_rebuild_required": event.prior_state != event.resulting_state,
        "edge_count": edge_count,
        "dependent_object_ids": sorted({str(item) for item in dependent_ids}),
        "immutable_dossier_ids": sorted(dossier_ids),
    }
    report = EvidenceLifecycleImpactReport(
        event_id=event.id,
        object_id=object_id,
        impact=impact,
        record_digest=digest_document({"event_digest": event.record_digest, "impact": impact}),
    )
    db.add(report)
    db.flush()
    return report
