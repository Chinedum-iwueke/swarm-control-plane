from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.institutional_lifecycle import (
    InstitutionalLifecycleEvent,
    InstitutionalLifecycleProjection,
)
from app.schemas.authority import AuthorityResolutionRequest
from app.schemas.institutional_lifecycle import (
    InstitutionalTransitionCreate,
    LifecycleSubjectCreate,
)
from app.services.authority import resolve_authority
from app.services.candidate_lifecycle_gate import require_risk004_evidence

INITIAL_STATES = {
    "research": "proposed",
    "evidence": "unassessed",
    "operations": "not-considered",
    "capital": "no-authority",
}

TRANSITIONS = {
    "research": {
        ("proposed", "register"): "registered",
        ("registered", "start"): "running",
        ("running", "succeed"): "succeeded",
        ("running", "fail"): "failed",
        ("proposed", "reject"): "rejected",
        ("registered", "reject"): "rejected",
    },
    "evidence": {
        ("unassessed", "admit"): "admissible",
        ("unassessed", "dispute"): "disputed",
        ("unassessed", "invalidate"): "invalid",
        ("disputed", "admit"): "admissible",
        ("disputed", "invalidate"): "invalid",
        ("admissible", "retract"): "retracted",
        ("admissible", "retire"): "retired",
    },
    "operations": {
        ("not-considered", "nominate"): "candidate",
        ("candidate", "approve"): "approved",
        ("approved", "start-shadow"): "shadow",
        ("shadow", "start-demo"): "demo",
        ("demo", "start-live"): "live",
        ("candidate", "reject"): "rejected",
        ("approved", "revoke"): "revoked",
        ("shadow", "suspend"): "suspended",
        ("demo", "suspend"): "suspended",
        ("live", "suspend"): "suspended",
        ("suspended", "retire"): "retired",
    },
    "capital": {
        ("no-authority", "qualify"): "eligible",
        ("eligible", "allocate"): "allocated",
        ("allocated", "reduce"): "reduced",
        ("allocated", "halt"): "revoked",
        ("reduced", "halt"): "revoked",
        ("eligible", "revoke"): "revoked",
    },
}

AUTHORITY_ACTIONS = {
    "research": ("experiment-execution", "authorize"),
    "evidence": ("evidence-admissibility", "admit"),
    "operations": ("production-eligibility", "approve"),
    "capital": ("capital-allocation", "allocate"),
}

COMMAND_AUTHORITY_ACTIONS = {
    ("research", "fail"): ("experiment-execution", "halt"),
    ("research", "reject"): ("research-program-charter", "reject"),
    ("evidence", "dispute"): ("evidence-admissibility", "quarantine"),
    ("evidence", "invalidate"): ("evidence-admissibility", "reject"),
    ("evidence", "retract"): ("evidence-admissibility", "reject"),
    ("evidence", "retire"): ("evidence-admissibility", "reject"),
    ("operations", "reject"): ("production-eligibility", "revoke"),
    ("operations", "revoke"): ("production-eligibility", "revoke"),
    ("operations", "suspend"): ("production-eligibility", "revoke"),
    ("operations", "retire"): ("production-eligibility", "revoke"),
    ("capital", "reduce"): ("capital-allocation", "reduce"),
    ("capital", "halt"): ("capital-allocation", "halt"),
    ("capital", "revoke"): ("capital-allocation", "halt"),
}


def digest_document(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def create_subject(
    db: Session, payload: LifecycleSubjectCreate
) -> list[InstitutionalLifecycleProjection]:
    existing = _projections(db, payload.subject_type, payload.subject_id)
    if existing:
        if any(item.subject_digest != payload.subject_digest for item in existing):
            raise HTTPException(
                status_code=409, detail="Lifecycle subject digest is immutable."
            )
        return existing
    records = [
        InstitutionalLifecycleProjection(
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            subject_digest=payload.subject_digest,
            dimension=dimension,
            state=state,
            version=0,
        )
        for dimension, state in INITIAL_STATES.items()
    ]
    db.add_all(records)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _projections(db, payload.subject_type, payload.subject_id)
        if len(existing) != len(INITIAL_STATES) or any(
            item.subject_digest != payload.subject_digest for item in existing
        ):
            raise HTTPException(
                status_code=409, detail="Concurrent lifecycle registration conflicted."
            ) from None
        return existing
    return _projections(db, payload.subject_type, payload.subject_id)


def transition(
    db: Session,
    subject_type: str,
    subject_id: str,
    payload: InstitutionalTransitionCreate,
) -> tuple[InstitutionalLifecycleProjection, InstitutionalLifecycleEvent]:
    replay = db.scalar(
        select(InstitutionalLifecycleEvent).where(
            InstitutionalLifecycleEvent.command_id == payload.command_id
        )
    )
    if replay is not None:
        projection = db.get(InstitutionalLifecycleProjection, replay.projection_id)
        if (
            projection is None
            or projection.subject_type != subject_type
            or projection.subject_id != subject_id
            or replay.dimension != payload.dimension
            or replay.command != payload.command
            or replay.expected_version != payload.expected_version
        ):
            raise HTTPException(
                status_code=409,
                detail="Command identity was reused with different content.",
            )
        return projection, replay

    projection = db.scalar(
        select(InstitutionalLifecycleProjection)
        .where(
            InstitutionalLifecycleProjection.subject_type == subject_type,
            InstitutionalLifecycleProjection.subject_id == subject_id,
            InstitutionalLifecycleProjection.dimension == payload.dimension,
        )
        .with_for_update()
    )
    if projection is None:
        raise HTTPException(
            status_code=404, detail="Lifecycle subject or dimension not found."
        )
    if projection.subject_digest != payload.subject_digest:
        raise HTTPException(status_code=409, detail="Lifecycle subject digest changed.")
    validate_expected_version(projection.version, payload.expected_version)
    if payload.effective_at > datetime.now(UTC) + timedelta(seconds=30):
        raise HTTPException(
            status_code=422, detail="Lifecycle event cannot take effect in the future."
        )
    if any(
        len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
        for item in payload.evidence
    ):
        raise HTTPException(
            status_code=422, detail="Evidence references must be SHA-256 digests."
        )
    resulting_state = next_state(payload.dimension, projection.state, payload.command)

    if payload.dimension == "capital" and payload.command in {"qualify", "allocate"}:
        require_risk004_evidence(
            db,
            subject_type=subject_type,
            subject_digest=payload.subject_digest,
            requested_action="allocate",
            evidence=payload.evidence,
        )

    all_projections = _projections(db, subject_type, subject_id)
    current = {item.dimension: item.state for item in all_projections}
    validate_cross_dimension_guard(payload.dimension, payload.command, current)
    if (
        payload.dimension in {"evidence", "operations", "capital"}
        and not payload.originator
    ):
        raise HTTPException(
            status_code=422,
            detail=f"{payload.dimension} transitions require an explicit originator.",
        )
    decision_type, action = COMMAND_AUTHORITY_ACTIONS.get(
        (payload.dimension, payload.command), AUTHORITY_ACTIONS[payload.dimension]
    )
    authority = resolve_authority(
        db,
        AuthorityResolutionRequest(
            actor=payload.actor,
            decision_type=decision_type,
            action=action,
            object_type=subject_type,
            object_id=subject_id,
            object_digest=payload.subject_digest,
            scope={"dimension": payload.dimension, "command": payload.command},
            risk_level=payload.risk_level,
            environment=payload.environment,
            requester=payload.requester,
            originator=payload.originator,
            evaluator=payload.evaluator,
            active_veto_roles=payload.active_veto_roles,
            exception_id=payload.authority_exception_id,
        ),
    )
    body = {
        "command_id": str(payload.command_id),
        "subject_type": subject_type,
        "subject_id": subject_id,
        "subject_digest": payload.subject_digest,
        "dimension": payload.dimension,
        "command": payload.command,
        "prior_state": projection.state,
        "resulting_state": resulting_state,
        "expected_version": payload.expected_version,
        "resulting_version": projection.version + 1,
        "actor": payload.actor,
        "authority_decision_id": str(authority.id),
        "evidence": payload.evidence,
        "reason": payload.reason,
        "prior_event_digest": projection.last_event_digest,
        "effective_at": payload.effective_at.isoformat(),
    }
    event = InstitutionalLifecycleEvent(
        projection_id=projection.id,
        command_id=payload.command_id,
        dimension=payload.dimension,
        command=payload.command,
        prior_state=projection.state,
        resulting_state=resulting_state,
        actor=payload.actor,
        authority_decision_id=authority.id,
        expected_version=projection.version,
        resulting_version=projection.version + 1,
        reason=payload.reason,
        evidence=payload.evidence,
        prior_event_digest=projection.last_event_digest,
        record_digest=digest_document(body),
        effective_at=payload.effective_at,
    )
    projection.state = resulting_state
    projection.version += 1
    projection.last_event_digest = event.record_digest
    projection.updated_at = datetime.now(UTC)
    db.add(event)
    db.commit()
    db.refresh(projection)
    db.refresh(event)
    return projection, event


def lifecycle_dossier(
    db: Session, subject_type: str, subject_id: str
) -> dict[str, Any]:
    projections = _projections(db, subject_type, subject_id)
    if not projections:
        raise HTTPException(status_code=404, detail="Lifecycle subject not found.")
    projection_ids = [item.id for item in projections]
    events = list(
        db.scalars(
            select(InstitutionalLifecycleEvent)
            .where(InstitutionalLifecycleEvent.projection_id.in_(projection_ids))
            .order_by(
                InstitutionalLifecycleEvent.created_at, InstitutionalLifecycleEvent.id
            )
        ).all()
    )
    _verify_replay(projections, events)
    material = {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "subject_digest": projections[0].subject_digest,
        "projections": [
            {
                "dimension": item.dimension,
                "state": item.state,
                "version": item.version,
                "last_event_digest": item.last_event_digest,
            }
            for item in projections
        ],
        "events": [item.record_digest for item in events],
    }
    return {
        **material,
        "projections": projections,
        "events": events,
        "dossier_digest": digest_document(material),
    }


def list_projections(
    db: Session, limit: int = 200
) -> list[InstitutionalLifecycleProjection]:
    return list(
        db.scalars(
            select(InstitutionalLifecycleProjection)
            .order_by(InstitutionalLifecycleProjection.updated_at.desc())
            .limit(limit)
        ).all()
    )


def _projections(
    db: Session, subject_type: str, subject_id: str
) -> list[InstitutionalLifecycleProjection]:
    return list(
        db.scalars(
            select(InstitutionalLifecycleProjection)
            .where(
                InstitutionalLifecycleProjection.subject_type == subject_type,
                InstitutionalLifecycleProjection.subject_id == subject_id,
            )
            .order_by(InstitutionalLifecycleProjection.dimension)
        ).all()
    )


def next_state(dimension: str, state: str, command: str) -> str:
    resulting_state = TRANSITIONS[dimension].get((state, command))
    if resulting_state is None:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "invalid-transition",
                "dimension": dimension,
                "state": state,
                "command": command,
            },
        )
    return resulting_state


def validate_expected_version(current_version: int, expected_version: int) -> None:
    if current_version != expected_version:
        raise HTTPException(
            status_code=409,
            detail={"reason": "stale-version", "current_version": current_version},
        )


def validate_cross_dimension_guard(
    dimension: str, command: str, states: dict[str, str]
) -> None:
    if (
        dimension == "operations"
        and command
        in {"nominate", "approve", "start-shadow", "start-demo", "start-live"}
        and (states["research"] != "succeeded" or states["evidence"] != "admissible")
    ):
        raise HTTPException(
            status_code=409,
            detail="Operations progression requires succeeded research and admissible evidence.",
        )
    if (
        dimension == "capital"
        and command in {"qualify", "allocate"}
        and (states["operations"] != "live" or states["evidence"] != "admissible")
    ):
        raise HTTPException(
            status_code=409,
            detail="Capital progression requires live operations and admissible evidence.",
        )


def _verify_replay(
    projections: list[InstitutionalLifecycleProjection],
    events: list[InstitutionalLifecycleEvent],
) -> None:
    by_dimension: dict[str, list[InstitutionalLifecycleEvent]] = {
        key: [] for key in INITIAL_STATES
    }
    projection_by_id = {item.id: item for item in projections if hasattr(item, "id")}
    for event in events:
        by_dimension[event.dimension].append(event)
        projection = projection_by_id.get(getattr(event, "projection_id", None))
        if (
            projection is not None
            and digest_document(_event_material(projection, event))
            != event.record_digest
        ):
            raise HTTPException(
                status_code=409, detail="Lifecycle event digest is invalid."
            )
    for projection in projections:
        state = INITIAL_STATES[projection.dimension]
        version = 0
        prior_digest = None
        for event in by_dimension[projection.dimension]:
            if (
                event.prior_state != state
                or event.expected_version != version
                or event.prior_event_digest != prior_digest
            ):
                raise HTTPException(
                    status_code=409, detail="Lifecycle event history is not replayable."
                )
            state = event.resulting_state
            version = event.resulting_version
            prior_digest = event.record_digest
        if (projection.state, projection.version, projection.last_event_digest) != (
            state,
            version,
            prior_digest,
        ):
            raise HTTPException(
                status_code=409,
                detail="Lifecycle projection does not match event history.",
            )


def _event_material(
    projection: InstitutionalLifecycleProjection,
    event: InstitutionalLifecycleEvent,
) -> dict[str, Any]:
    return {
        "command_id": str(event.command_id),
        "subject_type": projection.subject_type,
        "subject_id": projection.subject_id,
        "subject_digest": projection.subject_digest,
        "dimension": event.dimension,
        "command": event.command,
        "prior_state": event.prior_state,
        "resulting_state": event.resulting_state,
        "expected_version": event.expected_version,
        "resulting_version": event.resulting_version,
        "actor": event.actor,
        "authority_decision_id": str(event.authority_decision_id),
        "evidence": event.evidence,
        "reason": event.reason,
        "prior_event_digest": event.prior_event_digest,
        "effective_at": event.effective_at.isoformat(),
    }
