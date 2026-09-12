from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.demo_certification_schema import DemoCertificationSchemaRegistry
from app.schemas.demo_certification_schema import (
    DemoCertificationSchemaCreate,
    DemoCertificationSchemaResponse,
)
from app.services.demo_certification_schema import (
    DemoCertificationSchemaConflict,
    register_demo_certification_schema,
)

router = APIRouter(
    prefix="/v1/research/demo-certification-schemas",
    tags=["research-demo-certification-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=DemoCertificationSchemaResponse, status_code=201)
def create_demo_certification_schema(payload: DemoCertificationSchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_demo_certification_schema(db, payload)
        db.commit()
        db.refresh(record)
        return DemoCertificationSchemaResponse.model_validate(record)
    except DemoCertificationSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[DemoCertificationSchemaResponse])
def list_demo_certification_schemas(db: Annotated[Session, Depends(get_db)]):
    return [DemoCertificationSchemaResponse.model_validate(item) for item in db.scalars(
        select(DemoCertificationSchemaRegistry).order_by(DemoCertificationSchemaRegistry.registered_at)
    ).all()]


@router.get("/{schema_id}", response_model=DemoCertificationSchemaResponse)
def get_demo_certification_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(DemoCertificationSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Demo-certification schema not found.")
    return DemoCertificationSchemaResponse.model_validate(record)
