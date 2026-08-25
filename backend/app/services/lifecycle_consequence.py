from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.institutional_lifecycle import (
    InstitutionalLifecycleEvent,
    InstitutionalLifecycleProjection,
)
from app.models.lifecycle_consequence import LifecycleConsequence
from app.schemas.authority import AuthorityResolutionRequest
from app.schemas.lifecycle_consequence import ConsequenceCreate, ConsequenceReverse
from app.services.authority import resolve_authority
from app.services.institutional_lifecycle import (
    digest_document,
    validate_cross_dimension_guard,
    validate_expected_version,
)

CONSEQUENCE_STATES = {
    "research": {
        ("proposed", "quarantine"): "rejected",
        ("registered", "quarantine"): "rejected",
        ("running", "quarantine"): "failed",
        ("succeeded", "retire"): "retired",
        ("failed", "retire"): "retired",
        ("rejected", "retire"): "retired",
        ("rejected", "reinstate"): "proposed",
        ("retired", "reinstate"): "proposed",
    },
    "evidence": {
        ("unassessed", "quarantine"): "disputed",
        ("admissible", "quarantine"): "disputed",
        ("admissible", "retire"): "retired",
        ("disputed", "retire"): "retired",
        ("retracted", "retire"): "retired",
        ("disputed", "reinstate"): "admissible",
        ("retracted", "reinstate"): "admissible",
        ("retired", "reinstate"): "admissible",
    },
    "operations": {
        ("candidate", "promote"): "approved",
        ("approved", "promote"): "shadow",
        ("shadow", "promote"): "demo",
        ("demo", "promote"): "live",
        ("live", "demote"): "demo",
        ("demo", "demote"): "shadow",
        ("shadow", "demote"): "approved",
        ("approved", "demote"): "candidate",
        ("candidate", "quarantine"): "suspended",
        ("approved", "quarantine"): "suspended",
        ("shadow", "quarantine"): "suspended",
        ("demo", "quarantine"): "suspended",
        ("live", "quarantine"): "suspended",
        ("suspended", "retire"): "retired",
        ("candidate", "retire"): "retired",
        ("approved", "retire"): "retired",
        ("shadow", "retire"): "retired",
        ("demo", "retire"): "retired",
        ("live", "retire"): "retired",
        ("suspended", "reinstate"): "candidate",
        ("retired", "reinstate"): "candidate",
        ("revoked", "reinstate"): "candidate",
    },
    "capital": {
        ("allocated", "demote"): "reduced",
        ("eligible", "quarantine"): "revoked",
        ("allocated", "quarantine"): "revoked",
        ("reduced", "retire"): "revoked",
        ("eligible", "retire"): "revoked",
        ("allocated", "retire"): "revoked",
        ("reduced", "reinstate"): "eligible",
        ("revoked", "reinstate"): "eligible",
    },
}

AUTHORITY = {
    "research": ("research-program-charter", "approve"),
    "evidence": ("evidence-admissibility", "quarantine"),
    "operations": ("candidate-maturity", "promote"),
    "capital": ("capital-allocation", "allocate"),
}


def consequence_state(dimension: str, state: str, action: str) -> str:
    result = CONSEQUENCE_STATES.get(dimension, {}).get((state, action))
    if result is None:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "invalid-consequence",
                "dimension": dimension,
                "state": state,
                "action": action,
            },
        )
    return result


def apply_consequence(
    db: Session, subject_type: str, subject_id: str, payload: ConsequenceCreate
) -> LifecycleConsequence:
    existing = db.scalar(
        select(LifecycleConsequence).where(
            LifecycleConsequence.command_id == payload.command_id
        )
    )
    if existing is not None:
        event = db.get(InstitutionalLifecycleEvent, existing.event_id)
        projection = db.get(InstitutionalLifecycleProjection, event.projection_id)
        if (
            existing.action != payload.action
            or event.dimension != payload.dimension
            or event.expected_version != payload.expected_version
            or projection.subject_type != subject_type
            or projection.subject_id != subject_id
            or projection.subject_digest != payload.subject_digest
        ):
            raise HTTPException(
                status_code=409, detail="Consequence command identity changed."
            )
        return existing
    projection = _locked_projection(db, subject_type, subject_id, payload.dimension)
    _validate_projection(projection, payload.subject_digest, payload.expected_version)
    resulting = consequence_state(payload.dimension, projection.state, payload.action)
    states = _states(db, subject_type, subject_id)
    if payload.action in {"promote", "reinstate"}:
        validate_cross_dimension_guard(
            payload.dimension,
            "nominate" if payload.dimension == "operations" else "qualify",
            states,
        )
    decision_type, action = _authority_for(payload.dimension, payload.action)
    authority = resolve_authority(
        db,
        AuthorityResolutionRequest(
            actor=payload.actor,
            decision_type=decision_type,
            action=action,
            object_type=subject_type,
            object_id=subject_id,
            object_digest=payload.subject_digest,
            scope={
                "dimension": payload.dimension,
                "consequence": payload.action,
                "approvers": payload.approvers,
            },
            risk_level=payload.risk_level,
            environment=payload.environment,
            originator=payload.originator,
            evaluator=payload.evaluator,
            active_veto_roles=payload.active_veto_roles,
        ),
    )
    event = _event(
        db,
        projection,
        payload.command_id,
        payload.action,
        resulting,
        payload.actor,
        authority.id,
        payload.evidence,
        payload.reason,
    )
    body = {
        "command_id": str(payload.command_id),
        "event_digest": event.record_digest,
        "action": payload.action,
        "prior_state": event.prior_state,
        "resulting_state": resulting,
        "rollback_state": event.prior_state,
        "approvers": payload.approvers,
        "affected_descendants": payload.affected_descendants,
        "evidence_epoch": payload.evidence_epoch.isoformat(),
        "expires_at": payload.expires_at.isoformat(),
    }
    record = LifecycleConsequence(
        event_id=event.id,
        command_id=payload.command_id,
        action=payload.action,
        status="active",
        prior_state=event.prior_state,
        resulting_state=resulting,
        rollback_state=event.prior_state,
        approvers=payload.approvers,
        affected_descendants=payload.affected_descendants,
        evidence_epoch=payload.evidence_epoch,
        expires_at=payload.expires_at,
        reason=payload.reason,
        record_digest=digest_document(body),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def reverse_consequence(
    db: Session,
    consequence_id: UUID,
    payload: ConsequenceReverse,
    *,
    terminal_status: str = "reversed",
) -> LifecycleConsequence:
    replay = db.scalar(
        select(LifecycleConsequence).where(
            LifecycleConsequence.command_id == payload.command_id
        )
    )
    if replay is not None:
        if replay.status != "reversal" or replay.reversal_of_id != consequence_id:
            raise HTTPException(
                status_code=409, detail="Reversal command identity changed."
            )
        return replay
    original = db.scalar(
        select(LifecycleConsequence)
        .where(LifecycleConsequence.id == consequence_id)
        .with_for_update()
    )
    if original is None:
        raise HTTPException(status_code=404, detail="Consequence not found.")
    if original.status != "active":
        raise HTTPException(status_code=409, detail="Consequence is not active.")
    event = db.get(InstitutionalLifecycleEvent, original.event_id)
    projection = db.scalar(
        select(InstitutionalLifecycleProjection)
        .where(InstitutionalLifecycleProjection.id == event.projection_id)
        .with_for_update()
    )
    validate_expected_version(projection.version, payload.expected_version)
    if projection.state != original.resulting_state:
        raise HTTPException(
            status_code=409, detail="Projection moved after the consequence."
        )
    reverse_action = (
        "demote" if original.action in {"promote", "reinstate"} else "reinstate"
    )
    decision_type, action = _authority_for(projection.dimension, reverse_action)
    authority = resolve_authority(
        db,
        AuthorityResolutionRequest(
            actor=payload.actor,
            decision_type=decision_type,
            action=action,
            object_type=projection.subject_type,
            object_id=projection.subject_id,
            object_digest=projection.subject_digest,
            scope={"reverse_consequence_id": str(original.id)},
            risk_level=payload.risk_level,
            environment=payload.environment,
            originator=payload.originator,
            evaluator=payload.evaluator,
            active_veto_roles=payload.active_veto_roles,
        ),
    )
    reversal_event = _event(
        db,
        projection,
        payload.command_id,
        f"reverse-{original.action}",
        original.rollback_state,
        payload.actor,
        authority.id,
        [original.record_digest],
        payload.reason,
    )
    body = {
        "command_id": str(payload.command_id),
        "event_digest": reversal_event.record_digest,
        "action": "reverse",
        "reversal_of": str(original.id),
        "resulting_state": original.rollback_state,
    }
    reversal = LifecycleConsequence(
        id=uuid4(),
        event_id=reversal_event.id,
        command_id=payload.command_id,
        action=original.action,
        status="reversal",
        prior_state=original.resulting_state,
        resulting_state=original.rollback_state,
        rollback_state=original.resulting_state,
        approvers=[payload.actor],
        affected_descendants=original.affected_descendants,
        evidence_epoch=datetime.now(UTC),
        expires_at=original.expires_at,
        reversal_of_id=original.id,
        reason=payload.reason,
        record_digest=digest_document(body),
    )
    db.add(reversal)
    db.flush()
    original.status = terminal_status
    original.reversed_by_id = reversal.id
    db.commit()
    db.refresh(reversal)
    return reversal


def expire_consequence(
    db: Session, consequence_id: UUID, payload: ConsequenceReverse
) -> LifecycleConsequence:
    original = db.get(LifecycleConsequence, consequence_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Consequence not found.")
    expires_at = original.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at > datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Consequence has not expired.")
    return reverse_consequence(db, consequence_id, payload, terminal_status="expired")


def list_consequences(db: Session, limit: int = 200) -> list[LifecycleConsequence]:
    return list(
        db.scalars(
            select(LifecycleConsequence)
            .order_by(LifecycleConsequence.created_at.desc())
            .limit(limit)
        ).all()
    )


def _authority_for(dimension: str, action: str) -> tuple[str, str]:
    if dimension == "operations" and action == "quarantine":
        return "emergency-containment", "quarantine"
    decision_type, positive = AUTHORITY[dimension]
    if action in {"demote", "quarantine", "retire"}:
        return decision_type, {
            "research": "reject",
            "evidence": "quarantine",
            "operations": "retire" if action == "retire" else "demote",
            "capital": "reduce",
        }[dimension]
    if dimension == "evidence":
        return decision_type, "admit"
    return decision_type, positive


def _locked_projection(db, subject_type, subject_id, dimension):
    item = db.scalar(
        select(InstitutionalLifecycleProjection)
        .where(
            InstitutionalLifecycleProjection.subject_type == subject_type,
            InstitutionalLifecycleProjection.subject_id == subject_id,
            InstitutionalLifecycleProjection.dimension == dimension,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Lifecycle projection not found.")
    return item


def _validate_projection(projection, digest, version):
    if projection.subject_digest != digest:
        raise HTTPException(status_code=409, detail="Lifecycle subject digest changed.")
    validate_expected_version(projection.version, version)


def _states(db, subject_type, subject_id):
    rows = db.scalars(
        select(InstitutionalLifecycleProjection).where(
            InstitutionalLifecycleProjection.subject_type == subject_type,
            InstitutionalLifecycleProjection.subject_id == subject_id,
        )
    ).all()
    return {row.dimension: row.state for row in rows}


def _event(
    db,
    projection,
    command_id,
    command,
    resulting,
    actor,
    authority_id,
    evidence,
    reason,
):
    now = datetime.now(UTC)
    prior = projection.state
    body = {
        "command_id": str(command_id),
        "subject_type": projection.subject_type,
        "subject_id": projection.subject_id,
        "subject_digest": projection.subject_digest,
        "dimension": projection.dimension,
        "command": command,
        "prior_state": prior,
        "resulting_state": resulting,
        "expected_version": projection.version,
        "resulting_version": projection.version + 1,
        "actor": actor,
        "authority_decision_id": str(authority_id),
        "evidence": evidence,
        "reason": reason,
        "prior_event_digest": projection.last_event_digest,
        "effective_at": now.isoformat(),
    }
    event = InstitutionalLifecycleEvent(
        projection_id=projection.id,
        command_id=command_id,
        dimension=projection.dimension,
        command=command,
        prior_state=prior,
        resulting_state=resulting,
        actor=actor,
        authority_decision_id=authority_id,
        expected_version=projection.version,
        resulting_version=projection.version + 1,
        reason=reason,
        evidence=evidence,
        prior_event_digest=projection.last_event_digest,
        record_digest=digest_document(body),
        effective_at=now,
    )
    db.add(event)
    db.flush()
    projection.state = resulting
    projection.version += 1
    projection.last_event_digest = event.record_digest
    projection.updated_at = now
    return event
