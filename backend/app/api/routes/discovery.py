from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.discovery import DiscoveryMap, DiscoveryMapEvent
from app.schemas.discovery import (
    DiscoveryMapCreate,
    DiscoveryMapEventResponse,
    DiscoveryMapResponse,
)
from app.services.discovery import DiscoveryConflict, register_discovery_map

router = APIRouter(
    prefix="/v1/research/discovery-maps",
    tags=["research-discovery-maps"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=DiscoveryMapResponse, status_code=201)
def create_map(payload: DiscoveryMapCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_discovery_map(db, payload)
        db.commit()
        db.refresh(record)
        return DiscoveryMapResponse.model_validate(record)
    except DiscoveryConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[DiscoveryMapResponse])
def list_maps(
    db: Annotated[Session, Depends(get_db)],
    stage: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    statement = select(DiscoveryMap)
    if stage is not None:
        statement = statement.where(DiscoveryMap.stage == stage)
    if status is not None:
        statement = statement.where(DiscoveryMap.status == status)
    records = db.scalars(
        statement.order_by(DiscoveryMap.registered_at.desc()).limit(limit)
    ).all()
    return [DiscoveryMapResponse.model_validate(item) for item in records]


@router.get("/{map_id}", response_model=DiscoveryMapResponse)
def get_map(map_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(DiscoveryMap, map_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Discovery map not found.")
    return DiscoveryMapResponse.model_validate(record)


@router.get("/{map_id}/events", response_model=list[DiscoveryMapEventResponse])
def list_map_events(map_id: UUID, db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(DiscoveryMapEvent)
        .where(DiscoveryMapEvent.map_id == map_id)
        .order_by(DiscoveryMapEvent.recorded_at, DiscoveryMapEvent.id)
    ).all()
    return [DiscoveryMapEventResponse.model_validate(item) for item in records]
