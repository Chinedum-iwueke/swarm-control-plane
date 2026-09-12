from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.oms_schema import OmsSchemaRegistry
from app.schemas.oms_schema import OmsSchemaCreate, OmsSchemaResponse
from app.services.oms_schema import OmsSchemaConflict, register_oms_schema

router = APIRouter(prefix="/v1/research/oms-schemas", tags=["research-oms-schemas"], dependencies=[Depends(require_orchestrator)])


@router.post("", response_model=OmsSchemaResponse, status_code=201)
def create_oms_schema(payload: OmsSchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_oms_schema(db, payload)
        db.commit()
        db.refresh(record)
        return OmsSchemaResponse.model_validate(record)
    except OmsSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[OmsSchemaResponse])
def list_oms_schemas(db: Annotated[Session, Depends(get_db)]):
    return [OmsSchemaResponse.model_validate(item) for item in db.scalars(select(OmsSchemaRegistry).order_by(OmsSchemaRegistry.registered_at)).all()]


@router.get("/{schema_id}", response_model=OmsSchemaResponse)
def get_oms_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(OmsSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="OMS schema not found.")
    return OmsSchemaResponse.model_validate(record)
