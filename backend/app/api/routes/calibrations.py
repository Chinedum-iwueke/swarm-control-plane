from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.calibration import ModelCalibrationAssessment
from app.schemas.calibration import (
    CalibrationAssessmentCreate,
    CalibrationAssessmentResponse,
)
from app.services.calibration import CalibrationConflict, register_assessment

router = APIRouter(
    prefix="/v1/research/model-calibrations",
    tags=["research-model-calibrations"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=CalibrationAssessmentResponse, status_code=201)
def create_assessment(
    payload: CalibrationAssessmentCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_assessment(db, payload)
        db.commit()
        db.refresh(record)
        return CalibrationAssessmentResponse.model_validate(record)
    except CalibrationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[CalibrationAssessmentResponse])
def list_assessments(db: Annotated[Session, Depends(get_db)]):
    return [
        CalibrationAssessmentResponse.model_validate(item)
        for item in db.scalars(
            select(ModelCalibrationAssessment).order_by(
                ModelCalibrationAssessment.assessed_at.desc()
            )
        ).all()
    ]


@router.get("/{assessment_id}", response_model=CalibrationAssessmentResponse)
def get_assessment(assessment_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ModelCalibrationAssessment, assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Calibration assessment not found.")
    return CalibrationAssessmentResponse.model_validate(record)
