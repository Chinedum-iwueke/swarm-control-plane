from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.shadow_monitoring_schema import ShadowMonitoringSchemaRegistry
from app.schemas.shadow_monitoring_schema import (
    ShadowMonitoringSchemaCreate,
    ShadowMonitoringSchemaResponse,
)
from app.services.shadow_monitoring_schema import (
    ShadowMonitoringSchemaConflict,
    register_shadow_monitoring_schema,
)

router = APIRouter(
    prefix="/v1/research/shadow-monitoring-schemas",
    tags=["research-shadow-monitoring-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ShadowMonitoringSchemaResponse, status_code=201)
def create_shadow_monitoring_schema(
    payload: ShadowMonitoringSchemaCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_shadow_monitoring_schema(db, payload)
        db.commit()
        db.refresh(record)
        return ShadowMonitoringSchemaResponse.model_validate(record)
    except ShadowMonitoringSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ShadowMonitoringSchemaResponse])
def list_shadow_monitoring_schemas(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ShadowMonitoringSchemaRegistry).order_by(
            ShadowMonitoringSchemaRegistry.registered_at
        )
    ).all()
    return [ShadowMonitoringSchemaResponse.model_validate(item) for item in records]


@router.get("/{schema_id}", response_model=ShadowMonitoringSchemaResponse)
def get_shadow_monitoring_schema(
    schema_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ShadowMonitoringSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Shadow-monitoring schema not found."
        )
    return ShadowMonitoringSchemaResponse.model_validate(record)
