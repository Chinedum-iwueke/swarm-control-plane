from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.reference_data import ReferenceDataSnapshot
from app.schemas.reference_data import (
    ReferenceResolution,
    ReferenceResolveRequest,
    ReferenceSnapshotCreate,
    ReferenceSnapshotResponse,
)
from app.services.reference_data import (
    ReferenceDataConflict,
    ReferenceDataUnknown,
    register_reference_snapshot,
    resolve_registered_reference,
)

router = APIRouter(
    prefix="/v1/research/reference-data",
    tags=["research-reference-data"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/snapshots", response_model=ReferenceSnapshotResponse, status_code=201)
def create_snapshot(
    payload: ReferenceSnapshotCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_reference_snapshot(db, payload)
        db.commit()
        db.refresh(record)
        return ReferenceSnapshotResponse.model_validate(record)
    except ReferenceDataUnknown as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReferenceDataConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/snapshots", response_model=list[ReferenceSnapshotResponse])
def list_snapshots(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    records = db.scalars(
        select(ReferenceDataSnapshot)
        .order_by(ReferenceDataSnapshot.as_of.desc())
        .limit(limit)
    ).all()
    return [ReferenceSnapshotResponse.model_validate(record) for record in records]


@router.get("/snapshots/{snapshot_id}", response_model=ReferenceSnapshotResponse)
def get_snapshot(snapshot_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ReferenceDataSnapshot, snapshot_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Reference snapshot not found.")
    return ReferenceSnapshotResponse.model_validate(record)


@router.post("/resolve", response_model=ReferenceResolution)
def resolve_reference(
    payload: ReferenceResolveRequest, db: Annotated[Session, Depends(get_db)]
):
    try:
        return resolve_registered_reference(db, payload)
    except ReferenceDataUnknown as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReferenceDataConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
