from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.microstructure_model import MicrostructureModelRegistry
from app.schemas.microstructure_model import (
    MicrostructureModelCreate,
    MicrostructureModelResponse,
)
from app.services.microstructure_model import (
    MicrostructureModelConflict,
    register_model,
)

router = APIRouter(prefix="/v1/research/microstructure-models", tags=["research-microstructure-models"], dependencies=[Depends(require_orchestrator)])


@router.post("", response_model=MicrostructureModelResponse, status_code=201)
def create_model(payload: MicrostructureModelCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_model(db, payload)
        db.commit()
        db.refresh(record)
        return MicrostructureModelResponse.model_validate(record)
    except MicrostructureModelConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[MicrostructureModelResponse])
def list_models(db: Annotated[Session, Depends(get_db)]):
    return [MicrostructureModelResponse.model_validate(item) for item in db.scalars(
        select(MicrostructureModelRegistry).order_by(MicrostructureModelRegistry.registered_at)
    ).all()]


@router.get("/{model_id}", response_model=MicrostructureModelResponse)
def get_model(model_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(MicrostructureModelRegistry, model_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Microstructure model not found.")
    return MicrostructureModelResponse.model_validate(record)
