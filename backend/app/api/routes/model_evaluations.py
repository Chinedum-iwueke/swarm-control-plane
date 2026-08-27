from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.model_evaluation import ModelFamilyEvaluation
from app.schemas.model_evaluation import (
    ModelFamilyEvaluationCreate,
    ModelFamilyEvaluationResponse,
)
from app.services.model_evaluation import ModelEvaluationConflict, register_evaluation

router = APIRouter(
    prefix="/v1/research/model-evaluations",
    tags=["research-model-evaluations"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ModelFamilyEvaluationResponse, status_code=201)
def create_evaluation(
    payload: ModelFamilyEvaluationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_evaluation(db, payload)
        db.commit()
        db.refresh(record)
        return ModelFamilyEvaluationResponse.model_validate(record)
    except ModelEvaluationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[ModelFamilyEvaluationResponse])
def list_evaluations(db: Annotated[Session, Depends(get_db)]):
    return [
        ModelFamilyEvaluationResponse.model_validate(item)
        for item in db.scalars(
            select(ModelFamilyEvaluation).order_by(
                ModelFamilyEvaluation.evaluated_at.desc()
            )
        ).all()
    ]


@router.get("/{evaluation_id}", response_model=ModelFamilyEvaluationResponse)
def get_evaluation(evaluation_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ModelFamilyEvaluation, evaluation_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Model-family evaluation not found."
        )
    return ModelFamilyEvaluationResponse.model_validate(record)
