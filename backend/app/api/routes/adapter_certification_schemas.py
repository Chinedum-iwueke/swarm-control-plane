from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.adapter_certification_schema import AdapterCertificationSchemaRegistry
from app.schemas.adapter_certification_schema import (
    AdapterCertificationSchemaCreate,
    AdapterCertificationSchemaResponse,
)
from app.services.adapter_certification_schema import (
    AdapterCertificationSchemaConflict,
    register_adapter_certification_schema,
)

router = APIRouter(
    prefix="/v1/research/adapter-certification-schemas",
    tags=["research-adapter-certification-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=AdapterCertificationSchemaResponse, status_code=201)
def create_adapter_certification_schema(
    payload: AdapterCertificationSchemaCreate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        record = register_adapter_certification_schema(db, payload)
        db.commit()
        db.refresh(record)
        return AdapterCertificationSchemaResponse.model_validate(record)
    except AdapterCertificationSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[AdapterCertificationSchemaResponse])
def list_adapter_certification_schemas(db: Annotated[Session, Depends(get_db)]):
    return [
        AdapterCertificationSchemaResponse.model_validate(item)
        for item in db.scalars(
            select(AdapterCertificationSchemaRegistry).order_by(
                AdapterCertificationSchemaRegistry.registered_at
            )
        ).all()
    ]


@router.get("/{schema_id}", response_model=AdapterCertificationSchemaResponse)
def get_adapter_certification_schema(
    schema_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(AdapterCertificationSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Adapter-certification schema not found."
        )
    return AdapterCertificationSchemaResponse.model_validate(record)
