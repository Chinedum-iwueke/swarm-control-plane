import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.evaluator_routing import (
    EvaluationRoute,
    EvaluatorAssignment,
    EvaluatorProfile,
)
from app.schemas.evaluator_routing import (
    EvaluationRouteCreate,
    EvaluationRouteResponse,
    EvaluatorAssignmentComplete,
    EvaluatorProfileCreate,
    EvaluatorProfileResponse,
    IndependenceAssertionResponse,
)
from app.services.evaluator_routing import (
    complete_assignment,
    create_route,
    register_profile,
    require_independence,
    serialize_route,
)

router = APIRouter(
    prefix="/v1/evaluator-routing",
    tags=["independent-evaluator-routing"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/profiles",
    response_model=EvaluatorProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    payload: EvaluatorProfileCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        profile = register_profile(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Evaluator profile version or digest already exists."
        ) from exc
    db.refresh(profile)
    return profile


@router.get("/profiles", response_model=list[EvaluatorProfileResponse])
def list_profiles(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(EvaluatorProfile)
            .order_by(EvaluatorProfile.created_at.desc())
            .limit(100)
        ).all()
    )


@router.post(
    "/routes",
    response_model=EvaluationRouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def route(payload: EvaluationRouteCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = create_route(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This exact evaluation route already exists.") from exc
    db.refresh(record)
    return serialize_route(db, record)


@router.get("/routes", response_model=list[EvaluationRouteResponse])
def list_routes(
    db: Annotated[Session, Depends(get_db)],
    route_digest: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
):
    query = select(EvaluationRoute)
    if route_digest:
        query = query.where(EvaluationRoute.route_digest == route_digest)
    query = query.order_by(EvaluationRoute.created_at.desc()).limit(100)
    return [serialize_route(db, item) for item in db.scalars(query).all()]


@router.get("/routes/{route_id}", response_model=EvaluationRouteResponse)
def get_route(route_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(EvaluationRoute, route_id)
    if record is None:
        raise HTTPException(404, "Evaluation route not found.")
    return serialize_route(db, record)


@router.post(
    "/routes/{route_id}/assignments/{assignment_id}/complete",
    response_model=EvaluationRouteResponse,
)
def finish_assignment(
    route_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: EvaluatorAssignmentComplete,
    db: Annotated[Session, Depends(get_db)],
):
    record = db.scalar(
        select(EvaluationRoute).where(EvaluationRoute.id == route_id).with_for_update()
    )
    assignment = db.scalar(
        select(EvaluatorAssignment)
        .where(
            EvaluatorAssignment.id == assignment_id,
            EvaluatorAssignment.route_id == route_id,
        )
        .with_for_update()
    )
    if record is None or assignment is None:
        raise HTTPException(404, "Evaluation route or assignment not found.")
    complete_assignment(db, record, assignment, payload)
    db.commit()
    db.refresh(record)
    return serialize_route(db, record)


@router.get(
    "/routes/{route_id}/assertion", response_model=IndependenceAssertionResponse
)
def assertion(route_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(EvaluationRoute, route_id)
    if record is None:
        raise HTTPException(404, "Evaluation route not found.")
    receipt = require_independence(db, record)
    return IndependenceAssertionResponse(
        route_id=record.id,
        verdict=receipt.verdict,
        receipt_digest=receipt.receipt_digest,
        assertion=receipt.assertion,
    )
