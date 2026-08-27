from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.falsification import MechanismEvaluation, MechanismPlan
from app.schemas.falsification import (
    MechanismEvaluationCreate,
    MechanismEvaluationResponse,
    MechanismPlanCreate,
    MechanismPlanResponse,
)
from app.services.falsification import (
    FalsificationConflict,
    register_evaluation,
    register_plan,
)

router = APIRouter(
    prefix="/v1/research/falsification",
    tags=["research-falsification"],
    dependencies=[Depends(require_orchestrator)],
)


def _commit(db: Session, action):
    try:
        record = action()
        db.commit()
        db.refresh(record)
        return record
    except FalsificationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/plans", response_model=MechanismPlanResponse, status_code=201)
def create_plan(payload: MechanismPlanCreate, db: Annotated[Session, Depends(get_db)]):
    return MechanismPlanResponse.model_validate(
        _commit(db, lambda: register_plan(db, payload))
    )


@router.get("/plans", response_model=list[MechanismPlanResponse])
def list_plans(db: Annotated[Session, Depends(get_db)]):
    return [
        MechanismPlanResponse.model_validate(item)
        for item in db.scalars(
            select(MechanismPlan).order_by(MechanismPlan.registered_at.desc())
        ).all()
    ]


@router.post(
    "/evaluations", response_model=MechanismEvaluationResponse, status_code=201
)
def create_evaluation(
    payload: MechanismEvaluationCreate, db: Annotated[Session, Depends(get_db)]
):
    return MechanismEvaluationResponse.model_validate(
        _commit(db, lambda: register_evaluation(db, payload))
    )


@router.get("/evaluations", response_model=list[MechanismEvaluationResponse])
def list_evaluations(
    db: Annotated[Session, Depends(get_db)], plan_id: UUID | None = None
):
    statement = select(MechanismEvaluation)
    if plan_id:
        statement = statement.where(MechanismEvaluation.plan_id == plan_id)
    return [
        MechanismEvaluationResponse.model_validate(item)
        for item in db.scalars(
            statement.order_by(MechanismEvaluation.evaluated_at.desc())
        ).all()
    ]
