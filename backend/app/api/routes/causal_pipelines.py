from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.causal_pipeline import (
    CausalDatasetMaterialization,
    CausalDatasetPipeline,
)
from app.schemas.causal_pipeline import (
    CausalMaterializationCreate,
    CausalMaterializationResponse,
    CausalPipelineCreate,
    CausalPipelineResponse,
)
from app.services.causal_pipeline import (
    CausalPipelineConflict,
    register_materialization,
    register_pipeline,
)

router = APIRouter(
    prefix="/v1/research/causal-pipelines",
    tags=["research-causal-pipelines"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=CausalPipelineResponse, status_code=201)
def create_pipeline(
    payload: CausalPipelineCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_pipeline(db, payload)
        db.commit()
        db.refresh(record)
        return CausalPipelineResponse.model_validate(record)
    except CausalPipelineConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[CausalPipelineResponse])
def list_pipelines(db: Annotated[Session, Depends(get_db)]):
    return [
        CausalPipelineResponse.model_validate(item)
        for item in db.scalars(
            select(CausalDatasetPipeline).order_by(
                CausalDatasetPipeline.registered_at.desc()
            )
        ).all()
    ]


@router.get("/{pipeline_id}", response_model=CausalPipelineResponse)
def get_pipeline(pipeline_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(CausalDatasetPipeline, pipeline_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Causal pipeline not found.")
    return CausalPipelineResponse.model_validate(record)


@router.post(
    "/materializations", response_model=CausalMaterializationResponse, status_code=201
)
def create_materialization(
    payload: CausalMaterializationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_materialization(db, payload)
        db.commit()
        db.refresh(record)
        return CausalMaterializationResponse.model_validate(record)
    except CausalPipelineConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/materializations/{materialization_id}",
    response_model=CausalMaterializationResponse,
)
def get_materialization(
    materialization_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(CausalDatasetMaterialization, materialization_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Causal materialization not found.")
    return CausalMaterializationResponse.model_validate(record)
