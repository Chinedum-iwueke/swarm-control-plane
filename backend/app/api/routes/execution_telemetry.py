from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_telemetry import (
    ExecutionTelemetryReplay,
    ExecutionTelemetrySchemaRegistry,
)
from app.schemas.execution_telemetry import (
    ExecutionTelemetryOverview,
    ExecutionTelemetryReplayCreate,
    ExecutionTelemetryReplayResponse,
    ExecutionTelemetrySchemaCreate,
    ExecutionTelemetrySchemaResponse,
)
from app.services.execution_telemetry import (
    ExecutionTelemetryConflict,
    overview,
    register_replay,
    register_schema,
)

router = APIRouter(
    prefix="/v1/execution",
    tags=["execution-telemetry"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/telemetry-schemas",
    response_model=ExecutionTelemetrySchemaResponse,
    status_code=201,
)
def create_schema(
    payload: ExecutionTelemetrySchemaCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_schema(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ExecutionTelemetryConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/telemetry-schemas", response_model=list[ExecutionTelemetrySchemaResponse])
def list_schemas(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(
        select(ExecutionTelemetrySchemaRegistry).order_by(
            ExecutionTelemetrySchemaRegistry.registered_at
        )
    ).all()


@router.post(
    "/replays", response_model=ExecutionTelemetryReplayResponse, status_code=201
)
def create_replay(
    payload: ExecutionTelemetryReplayCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_replay(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ExecutionTelemetryConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/replays/{replay_id}", response_model=ExecutionTelemetryReplayResponse)
def get_replay(replay_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ExecutionTelemetryReplay, replay_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Execution telemetry replay not found."
        )
    return record


@router.get("/overview", response_model=ExecutionTelemetryOverview)
def get_overview(
    db: Annotated[Session, Depends(get_db)],
    environment: Annotated[Literal["shadow", "demo", "live"] | None, Query()] = None,
):
    return overview(db, environment)
