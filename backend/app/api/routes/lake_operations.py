from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.lake_operations import LakeGovernanceSnapshot, LakeOperationEvent
from app.schemas.lake_operations import (
    LakeAdmissionDecision,
    LakeAdmissionRequest,
    LakeEventResponse,
    LakeGovernanceCreate,
    LakeGovernanceResponse,
    PublicationActionRequest,
    PublicationState,
    RestoreRequest,
)
from app.services.lake_operations import (
    LakeOperationConflict,
    LakeOperationUnknown,
    disable_publication,
    evaluate_admission,
    register_lake_governance,
    restore_publication,
)

router = APIRouter(
    prefix="/v1/research/lake-operations",
    tags=["research-lake-operations"],
    dependencies=[Depends(require_orchestrator)],
)


def _translate(exc: Exception):
    if isinstance(exc, LakeOperationUnknown):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/snapshots", response_model=LakeGovernanceResponse, status_code=201)
def create_snapshot(
    payload: LakeGovernanceCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_lake_governance(db, payload)
        db.commit()
        db.refresh(record)
        return LakeGovernanceResponse.model_validate(record)
    except (LakeOperationUnknown, LakeOperationConflict) as exc:
        db.rollback()
        _translate(exc)


@router.get("/snapshots", response_model=list[LakeGovernanceResponse])
def list_snapshots(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    records = db.scalars(
        select(LakeGovernanceSnapshot)
        .order_by(LakeGovernanceSnapshot.as_of.desc())
        .limit(limit)
    ).all()
    return [LakeGovernanceResponse.model_validate(item) for item in records]


@router.post("/admissions", response_model=LakeAdmissionDecision)
def admit(payload: LakeAdmissionRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        result = evaluate_admission(db, payload)
        db.commit()
        return result
    except (LakeOperationUnknown, LakeOperationConflict) as exc:
        db.rollback()
        _translate(exc)


@router.post("/publications/disable", response_model=PublicationState)
def disable(payload: PublicationActionRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        result = disable_publication(db, payload)
        db.commit()
        return result
    except (LakeOperationUnknown, LakeOperationConflict) as exc:
        db.rollback()
        _translate(exc)


@router.post("/publications/restore", response_model=PublicationState)
def restore(payload: RestoreRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        result = restore_publication(db, payload)
        db.commit()
        return result
    except (LakeOperationUnknown, LakeOperationConflict) as exc:
        db.rollback()
        _translate(exc)


@router.get("/events", response_model=list[LakeEventResponse])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    snapshot_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    statement = select(LakeOperationEvent)
    if snapshot_id is not None:
        statement = statement.where(LakeOperationEvent.snapshot_id == snapshot_id)
    records = db.scalars(
        statement.order_by(LakeOperationEvent.recorded_at.desc()).limit(limit)
    ).all()
    return [LakeEventResponse.model_validate(item) for item in records]
