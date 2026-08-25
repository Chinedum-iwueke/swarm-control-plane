from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.institutional_lifecycle import (
    InstitutionalTransitionCreate,
    LifecycleDossierResponse,
    LifecycleProjectionListResponse,
    LifecycleSubjectCreate,
)
from app.services.institutional_lifecycle import (
    create_subject,
    lifecycle_dossier,
    list_projections,
    transition,
)

router = APIRouter(
    prefix="/v1/lifecycles",
    tags=["institutional-lifecycles"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/projections", response_model=LifecycleProjectionListResponse)
def read_projections(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    items = list_projections(db, limit)
    return LifecycleProjectionListResponse(items=items, count=len(items))


@router.post(
    "/subjects",
    response_model=LifecycleDossierResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_subject(
    payload: LifecycleSubjectCreate, db: Annotated[Session, Depends(get_db)]
):
    create_subject(db, payload)
    return lifecycle_dossier(db, payload.subject_type, payload.subject_id)


@router.get(
    "/subjects/{subject_type}/{subject_id}", response_model=LifecycleDossierResponse
)
def read_subject(
    subject_type: str, subject_id: str, db: Annotated[Session, Depends(get_db)]
):
    return lifecycle_dossier(db, subject_type, subject_id)


@router.post(
    "/subjects/{subject_type}/{subject_id}/transitions",
    response_model=LifecycleDossierResponse,
)
def transition_subject(
    subject_type: str,
    subject_id: str,
    payload: InstitutionalTransitionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    transition(db, subject_type, subject_id, payload)
    return lifecycle_dossier(db, subject_type, subject_id)
