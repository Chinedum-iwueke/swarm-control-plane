from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_event_schema import ExecutionEventSchemaRegistry
from app.schemas.execution_event_schema import (
    ExecutionEventSchemaCreate,
    ExecutionEventSchemaResponse,
)
from app.services.execution_event_schema import (
    ExecutionEventSchemaConflict,
    register_event_schema,
)

router = APIRouter(
    prefix="/v1/research/execution-event-schemas",
    tags=["research-execution-event-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ExecutionEventSchemaResponse, status_code=201)
def create_event_schema(payload: ExecutionEventSchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_event_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ExecutionEventSchemaResponse.model_validate(record)
    except ExecutionEventSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionEventSchemaResponse])
def list_event_schemas(db: Annotated[Session, Depends(get_db)]):
    return [
        ExecutionEventSchemaResponse.model_validate(item)
        for item in db.scalars(select(ExecutionEventSchemaRegistry).order_by(ExecutionEventSchemaRegistry.registered_at)).all()
    ]


@router.get("/{schema_id}", response_model=ExecutionEventSchemaResponse)
def get_event_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ExecutionEventSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution event schema not found.")
    return ExecutionEventSchemaResponse.model_validate(record)
