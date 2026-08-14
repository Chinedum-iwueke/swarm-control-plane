from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.curriculum import ResearchBrainEvaluation, ResearchDomainCurriculum
from app.schemas.curriculum import (
    BrainEvaluationCreate,
    BrainEvaluationResponse,
    DomainCurriculumCreate,
    DomainCurriculumResponse,
    DomainReadinessResponse,
)
from app.services.curriculum import (
    curriculum_response,
    domain_readiness,
    evaluate_curriculum,
    register_curriculum,
)

router = APIRouter(
    prefix="/v1/research/curricula",
    tags=["domain-curriculum"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=DomainCurriculumResponse, status_code=201)
def create_curriculum(
    payload: DomainCurriculumCreate, db: Annotated[Session, Depends(get_db)]
):
    return curriculum_response(register_curriculum(db, payload))


@router.get("", response_model=list[DomainCurriculumResponse])
def list_curricula(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchDomainCurriculum).order_by(
            ResearchDomainCurriculum.domain_key,
            ResearchDomainCurriculum.created_at.desc(),
        )
    ).all()
    return [curriculum_response(record) for record in records]


@router.get("/readiness", response_model=list[DomainReadinessResponse])
def list_readiness(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchDomainCurriculum)
        .distinct(ResearchDomainCurriculum.domain_key)
        .order_by(
            ResearchDomainCurriculum.domain_key,
            ResearchDomainCurriculum.created_at.desc(),
        )
    ).all()
    return [domain_readiness(db, record) for record in records]


@router.post(
    "/{curriculum_id}/evaluations",
    response_model=BrainEvaluationResponse,
    status_code=201,
)
def create_evaluation(
    curriculum_id: UUID,
    payload: BrainEvaluationCreate,
    db: Annotated[Session, Depends(get_db)],
):
    if payload.curriculum_id != curriculum_id:
        raise HTTPException(status_code=422, detail="Curriculum identity mismatch.")
    return evaluate_curriculum(db, payload)


@router.get(
    "/{curriculum_id}/evaluations", response_model=list[BrainEvaluationResponse]
)
def list_evaluations(curriculum_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(ResearchBrainEvaluation)
            .where(ResearchBrainEvaluation.curriculum_id == curriculum_id)
            .order_by(ResearchBrainEvaluation.evaluated_at.desc())
        )
    )


@router.get("/{curriculum_id}/readiness", response_model=DomainReadinessResponse)
def read_readiness(curriculum_id: UUID, db: Annotated[Session, Depends(get_db)]):
    curriculum = db.get(ResearchDomainCurriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    return domain_readiness(db, curriculum)
