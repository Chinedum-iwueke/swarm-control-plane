from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.execution_calibration_schema import ExecutionCalibrationSchemaRegistry
from app.schemas.execution_calibration_schema import (
    ExecutionCalibrationSchemaCreate,
    ExecutionCalibrationSchemaResponse,
)
from app.services.execution_calibration_schema import (
    ExecutionCalibrationSchemaConflict,
    register_execution_calibration_schema,
)

router = APIRouter(
    prefix="/v1/research/execution-calibration-schemas",
    tags=["research-execution-calibration-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ExecutionCalibrationSchemaResponse, status_code=201)
def create_execution_calibration_schema(
    payload: ExecutionCalibrationSchemaCreate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        record = register_execution_calibration_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ExecutionCalibrationSchemaResponse.model_validate(record)
    except ExecutionCalibrationSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionCalibrationSchemaResponse])
def list_execution_calibration_schemas(
    db: Annotated[Session, Depends(get_db)],
):
    records = db.scalars(
        select(ExecutionCalibrationSchemaRegistry).order_by(
            ExecutionCalibrationSchemaRegistry.registered_at
        )
    ).all()
    return [ExecutionCalibrationSchemaResponse.model_validate(item) for item in records]


@router.get("/{schema_id}", response_model=ExecutionCalibrationSchemaResponse)
def get_execution_calibration_schema(
    schema_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ExecutionCalibrationSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Execution-calibration schema not found."
        )
    return ExecutionCalibrationSchemaResponse.model_validate(record)
