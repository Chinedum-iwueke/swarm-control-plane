from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_safety_schema import ExecutionSafetySchemaRegistry
from app.schemas.execution_safety_schema import (
    ExecutionSafetySchemaCreate,
    ExecutionSafetySchemaResponse,
)
from app.services.execution_safety_schema import (
    ExecutionSafetySchemaConflict,
    register_execution_safety_schema,
)

router = APIRouter(prefix="/v1/research/execution-safety-schemas", tags=["research-execution-safety-schemas"], dependencies=[Depends(require_orchestrator)])


@router.post("", response_model=ExecutionSafetySchemaResponse, status_code=201)
def create_execution_safety_schema(payload: ExecutionSafetySchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_execution_safety_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ExecutionSafetySchemaResponse.model_validate(record)
    except ExecutionSafetySchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionSafetySchemaResponse])
def list_execution_safety_schemas(db: Annotated[Session, Depends(get_db)]):
    return [ExecutionSafetySchemaResponse.model_validate(item) for item in db.scalars(select(ExecutionSafetySchemaRegistry).order_by(ExecutionSafetySchemaRegistry.registered_at)).all()]


@router.get("/{schema_id}", response_model=ExecutionSafetySchemaResponse)
def get_execution_safety_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ExecutionSafetySchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution-safety schema not found.")
    return ExecutionSafetySchemaResponse.model_validate(record)
