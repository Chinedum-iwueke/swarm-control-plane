from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_schedule_schema import ExecutionScheduleSchemaRegistry
from app.schemas.execution_schedule_schema import (
    ExecutionScheduleSchemaCreate,
    ExecutionScheduleSchemaResponse,
)
from app.services.execution_schedule_schema import (
    ExecutionScheduleSchemaConflict,
    register_execution_schedule_schema,
)

router = APIRouter(
    prefix="/v1/research/execution-schedule-schemas",
    tags=["research-execution-schedule-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ExecutionScheduleSchemaResponse, status_code=201)
def create_execution_schedule_schema(
    payload: ExecutionScheduleSchemaCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_execution_schedule_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ExecutionScheduleSchemaResponse.model_validate(record)
    except ExecutionScheduleSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionScheduleSchemaResponse])
def list_execution_schedule_schemas(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ExecutionScheduleSchemaRegistry).order_by(
            ExecutionScheduleSchemaRegistry.registered_at
        )
    ).all()
    return [ExecutionScheduleSchemaResponse.model_validate(item) for item in records]


@router.get("/{schema_id}", response_model=ExecutionScheduleSchemaResponse)
def get_execution_schedule_schema(
    schema_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ExecutionScheduleSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Execution-schedule schema not found."
        )
    return ExecutionScheduleSchemaResponse.model_validate(record)
