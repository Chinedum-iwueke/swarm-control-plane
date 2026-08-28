from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.risk_rules import RiskRuleEvaluation
from app.schemas.risk_rules import RiskRuleEvaluationCreate, RiskRuleEvaluationResponse
from app.services.risk_rules import RiskRuleConflict, register_evaluation

router = APIRouter(
    prefix="/v1/research/risk-rule-evaluations",
    tags=["research-risk"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=RiskRuleEvaluationResponse, status_code=201)
def create_evaluation(
    payload: RiskRuleEvaluationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_evaluation(db, payload)
        db.commit()
        db.refresh(record)
        return RiskRuleEvaluationResponse.model_validate(record)
    except RiskRuleConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[RiskRuleEvaluationResponse])
def list_evaluations(db: Annotated[Session, Depends(get_db)]):
    return [
        RiskRuleEvaluationResponse.model_validate(item)
        for item in db.scalars(
            select(RiskRuleEvaluation).order_by(RiskRuleEvaluation.evaluated_at.desc())
        ).all()
    ]


@router.get("/{evaluation_id}", response_model=RiskRuleEvaluationResponse)
def get_evaluation(evaluation_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(RiskRuleEvaluation, evaluation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Risk rule evaluation not found.")
    return RiskRuleEvaluationResponse.model_validate(record)
