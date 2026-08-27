import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.autonomous_research import AutonomousResearchSession
from app.schemas.autonomous_research import (
    AutonomousResearchSessionCreate,
    AutonomousResearchSessionResponse,
    AutonomousSessionAction,
    AutonomousSessionCheckpoint,
    AutonomousSessionCloseout,
)
from app.services.autonomous_research import (
    activate_session,
    cancel_session,
    close_session,
    reconcile_session,
    record_checkpoint,
    register_session,
    serialize_session,
)

router = APIRouter(
    prefix="/v1/research/autonomous-sessions",
    tags=["bounded-autonomous-research"],
    dependencies=[Depends(require_orchestrator)],
)


def locked(db: Session, session_id: uuid.UUID) -> AutonomousResearchSession:
    session = db.scalar(
        select(AutonomousResearchSession)
        .where(AutonomousResearchSession.id == session_id)
        .with_for_update()
    )
    if session is None:
        raise HTTPException(404, "Autonomous research session not found.")
    return session


def response(db: Session, session: AutonomousResearchSession) -> AutonomousResearchSessionResponse:
    return AutonomousResearchSessionResponse.model_validate(serialize_session(db, session))


@router.post("", response_model=AutonomousResearchSessionResponse, status_code=status.HTTP_201_CREATED)
def create(payload: AutonomousResearchSessionCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        session = register_session(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Session key or immutable agenda already exists.") from exc
    db.refresh(session)
    return response(db, session)


@router.get("", response_model=list[AutonomousResearchSessionResponse])
def list_sessions(db: Annotated[Session, Depends(get_db)], limit: Annotated[int, Query(ge=1, le=100)] = 50):
    sessions = db.scalars(
        select(AutonomousResearchSession).order_by(AutonomousResearchSession.created_at.desc()).limit(limit)
    ).all()
    return [response(db, session) for session in sessions]


@router.get("/{session_id}", response_model=AutonomousResearchSessionResponse)
def get(session_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    session = db.get(AutonomousResearchSession, session_id)
    if session is None:
        raise HTTPException(404, "Autonomous research session not found.")
    return response(db, session)


@router.post("/{session_id}/activate", response_model=AutonomousResearchSessionResponse)
def activate(session_id: uuid.UUID, payload: AutonomousSessionAction, db: Annotated[Session, Depends(get_db)]):
    session = locked(db, session_id)
    activate_session(db, session, payload.actor)
    db.commit()
    db.refresh(session)
    return response(db, session)


@router.post("/{session_id}/checkpoints", response_model=AutonomousResearchSessionResponse)
def checkpoint(session_id: uuid.UUID, payload: AutonomousSessionCheckpoint, db: Annotated[Session, Depends(get_db)]):
    session = locked(db, session_id)
    record_checkpoint(db, session, payload)
    db.commit()
    db.refresh(session)
    return response(db, session)


@router.post("/{session_id}/reconcile", response_model=AutonomousResearchSessionResponse)
def reconcile(session_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    session = locked(db, session_id)
    reconcile_session(db, session)
    db.commit()
    db.refresh(session)
    return response(db, session)


@router.post("/{session_id}/closeout", response_model=AutonomousResearchSessionResponse)
def closeout(session_id: uuid.UUID, payload: AutonomousSessionCloseout, db: Annotated[Session, Depends(get_db)]):
    session = locked(db, session_id)
    close_session(db, session, payload)
    db.commit()
    db.refresh(session)
    return response(db, session)


@router.post("/{session_id}/cancel", response_model=AutonomousResearchSessionResponse)
def cancel(session_id: uuid.UUID, payload: AutonomousSessionAction, db: Annotated[Session, Depends(get_db)]):
    session = locked(db, session_id)
    cancel_session(db, session, payload.actor, payload.reason)
    db.commit()
    db.refresh(session)
    return response(db, session)
