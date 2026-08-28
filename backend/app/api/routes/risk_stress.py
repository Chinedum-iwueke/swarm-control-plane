from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.risk_stress import RiskStressAssessment
from app.schemas.risk_stress import (
    RiskStressAssessmentCreate,
    RiskStressAssessmentResponse,
)
from app.services.risk_stress import RiskStressConflict, register_assessment

router = APIRouter(
    prefix="/v1/research/risk-stress-assessments",
    tags=["research-risk"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=RiskStressAssessmentResponse, status_code=201)
def create_assessment(
    payload: RiskStressAssessmentCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_assessment(db, payload)
        db.commit()
        db.refresh(record)
        return RiskStressAssessmentResponse.model_validate(record)
    except RiskStressConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[RiskStressAssessmentResponse])
def list_assessments(db: Annotated[Session, Depends(get_db)]):
    return [
        RiskStressAssessmentResponse.model_validate(item)
        for item in db.scalars(
            select(RiskStressAssessment).order_by(
                RiskStressAssessment.assessed_at.desc()
            )
        ).all()
    ]


@router.get("/{assessment_id}", response_model=RiskStressAssessmentResponse)
def get_assessment(assessment_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(RiskStressAssessment, assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Risk stress assessment not found.")
    return RiskStressAssessmentResponse.model_validate(record)
