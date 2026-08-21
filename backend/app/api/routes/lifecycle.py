from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.lifecycle import (
    DeletionDecisionCreate,
    DeletionRequestCreate,
    DeletionRequestResponse,
    LifecycleActionCreate,
    LifecycleDossierResponse,
    LifecycleStateListResponse,
    RetentionHoldCreate,
)
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.lifecycle import (
    apply_lifecycle_action,
    decide_deletion,
    lifecycle_dossier,
    list_lifecycle_states,
    request_deletion,
    set_retention_hold,
)

router = APIRouter(
    prefix="/v1/research/evidence/lifecycle",
    tags=["evidence-lifecycle"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/objects", response_model=LifecycleStateListResponse)
def read_lifecycle_states(
    db: Annotated[Session, Depends(get_db)],
    include_active: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    records = list_lifecycle_states(
        db, ORCHESTRATOR_ACCESS, include_active=include_active, limit=limit
    )
    return LifecycleStateListResponse(items=records, count=len(records))


@router.post("/objects/{object_id}/actions", response_model=LifecycleDossierResponse)
def transition_object(
    object_id: UUID,
    payload: LifecycleActionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    apply_lifecycle_action(db, object_id, payload, ORCHESTRATOR_ACCESS)
    return lifecycle_dossier(db, object_id, ORCHESTRATOR_ACCESS)


@router.post("/objects/{object_id}/retention-hold", response_model=LifecycleDossierResponse)
def update_retention_hold(
    object_id: UUID,
    payload: RetentionHoldCreate,
    db: Annotated[Session, Depends(get_db)],
):
    set_retention_hold(db, object_id, payload, ORCHESTRATOR_ACCESS)
    return lifecycle_dossier(db, object_id, ORCHESTRATOR_ACCESS)


@router.post(
    "/objects/{object_id}/deletion-requests",
    response_model=DeletionRequestResponse,
    status_code=201,
)
def create_deletion_request(
    object_id: UUID,
    payload: DeletionRequestCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return request_deletion(db, object_id, payload, ORCHESTRATOR_ACCESS)


@router.post(
    "/deletion-requests/{request_id}/decision",
    response_model=DeletionRequestResponse,
)
def decide_deletion_request(
    request_id: UUID,
    payload: DeletionDecisionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    request, _, _ = decide_deletion(db, request_id, payload, ORCHESTRATOR_ACCESS)
    return request


@router.get("/objects/{object_id}", response_model=LifecycleDossierResponse)
def read_lifecycle_dossier(
    object_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    return lifecycle_dossier(db, object_id, ORCHESTRATOR_ACCESS)
