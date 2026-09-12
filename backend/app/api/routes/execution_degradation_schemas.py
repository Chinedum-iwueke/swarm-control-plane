from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_degradation_schema import ExecutionDegradationSchemaRegistry
from app.schemas.execution_degradation_schema import (
    ExecutionDegradationSchemaCreate,
    ExecutionDegradationSchemaResponse,
)
from app.services.execution_degradation_schema import (
    ExecutionDegradationSchemaConflict,
    register_execution_degradation_schema,
)

router = APIRouter(
    prefix="/v1/research/execution-degradation-schemas",
    tags=["research-execution-degradation-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ExecutionDegradationSchemaResponse, status_code=201)
def create_execution_degradation_schema(
    payload: ExecutionDegradationSchemaCreate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        record = register_execution_degradation_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ExecutionDegradationSchemaResponse.model_validate(record)
    except ExecutionDegradationSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionDegradationSchemaResponse])
def list_execution_degradation_schemas(db: Annotated[Session, Depends(get_db)]):
    return [
        ExecutionDegradationSchemaResponse.model_validate(item)
        for item in db.scalars(
            select(ExecutionDegradationSchemaRegistry).order_by(
                ExecutionDegradationSchemaRegistry.registered_at
            )
        ).all()
    ]


@router.get("/{schema_id}", response_model=ExecutionDegradationSchemaResponse)
def get_execution_degradation_schema(
    schema_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ExecutionDegradationSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Execution-degradation schema not found."
        )
    return ExecutionDegradationSchemaResponse.model_validate(record)
