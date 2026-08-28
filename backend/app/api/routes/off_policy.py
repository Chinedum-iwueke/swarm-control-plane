from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.off_policy import OffPolicyProposalEvaluation
from app.schemas.off_policy import (
    OffPolicyEvaluationCreate,
    OffPolicyEvaluationResponse,
)
from app.services.off_policy import OffPolicyConflict, register_evaluation

router = APIRouter(
    prefix="/v1/research/off-policy-evaluations",
    tags=["research-off-policy"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=OffPolicyEvaluationResponse, status_code=201)
def create_evaluation(
    payload: OffPolicyEvaluationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_evaluation(db, payload)
        db.commit()
        db.refresh(record)
        return OffPolicyEvaluationResponse.model_validate(record)
    except OffPolicyConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[OffPolicyEvaluationResponse])
def list_evaluations(db: Annotated[Session, Depends(get_db)]):
    return [
        OffPolicyEvaluationResponse.model_validate(item)
        for item in db.scalars(
            select(OffPolicyProposalEvaluation).order_by(
                OffPolicyProposalEvaluation.evaluated_at.desc()
            )
        ).all()
    ]


@router.get("/{evaluation_id}", response_model=OffPolicyEvaluationResponse)
def get_evaluation(evaluation_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(OffPolicyProposalEvaluation, evaluation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Off-policy evaluation not found.")
    return OffPolicyEvaluationResponse.model_validate(record)
