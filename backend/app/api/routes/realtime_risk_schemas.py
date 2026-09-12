from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.realtime_risk_schema import RealtimeRiskSchemaRegistry
from app.schemas.realtime_risk_schema import (
    RealtimeRiskSchemaCreate,
    RealtimeRiskSchemaResponse,
)
from app.services.realtime_risk_schema import (
    RealtimeRiskSchemaConflict,
    register_realtime_risk_schema,
)

router = APIRouter(
    prefix="/v1/research/realtime-risk-schemas",
    tags=["research-realtime-risk-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=RealtimeRiskSchemaResponse, status_code=201)
def create(payload: RealtimeRiskSchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_realtime_risk_schema(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except RealtimeRiskSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[RealtimeRiskSchemaResponse])
def list_schemas(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(RealtimeRiskSchemaRegistry).order_by(
                RealtimeRiskSchemaRegistry.registered_at
            )
        ).all()
    )


@router.get("/{schema_id}", response_model=RealtimeRiskSchemaResponse)
def get(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(RealtimeRiskSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Real-time risk schema not found.")
    return record
