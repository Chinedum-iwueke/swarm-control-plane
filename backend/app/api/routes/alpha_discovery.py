from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.alpha_discovery import AlphaFounderResearchIdea, AlphaResearchMandate
from app.schemas.alpha_discovery import (
    AlphaDiscoveryGroundingRecovery,
    AlphaDiscoveryOverview,
    AlphaDiscoveryStageRetry,
    AlphaFounderResearchIdeaCreate,
    AlphaFounderResearchIdeaResponse,
    AlphaResearchMandateApproval,
    AlphaResearchMandateCreate,
    AlphaResearchMandateResponse,
)
from app.services.alpha_discovery import (
    approve_mandate,
    overview,
    queue_founder_idea,
    reconcile_mandate,
    recover_discovery_grounding,
    register_mandate,
    retry_invalid_discovery_stage,
    serialize_mandate,
)


def _serialize_idea(item: AlphaFounderResearchIdea) -> dict:
    return {
        key: getattr(item, key)
        for key in (
            "id",
            "mandate_id",
            "cycle_id",
            "conversation_id",
            "submitted_by",
            "idea",
            "constraints",
            "idea_digest",
            "status",
            "created_at",
            "updated_at",
        )
    }


router = APIRouter(
    prefix="/v1/research/alpha-discovery",
    tags=["continuous-alpha-discovery"],
    dependencies=[Depends(require_orchestrator)],
)


def _locked(db: Session, mandate_id: UUID) -> AlphaResearchMandate:
    mandate = db.scalar(
        select(AlphaResearchMandate)
        .where(AlphaResearchMandate.id == mandate_id)
        .with_for_update()
    )
    if mandate is None:
        raise HTTPException(404, "Alpha research mandate not found.")
    return mandate


@router.post(
    "/mandates",
    response_model=AlphaResearchMandateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mandate(
    payload: AlphaResearchMandateCreate,
    db: Annotated[Session, Depends(get_db)],
):
    mandate = register_mandate(db, payload)
    db.commit()
    db.refresh(mandate)
    return serialize_mandate(mandate)


@router.get("/mandates", response_model=list[AlphaResearchMandateResponse])
def list_mandates(db: Annotated[Session, Depends(get_db)]):
    mandates = db.scalars(
        select(AlphaResearchMandate).order_by(AlphaResearchMandate.created_at.desc())
    ).all()
    return [serialize_mandate(item) for item in mandates]


@router.post("/ideas", response_model=AlphaFounderResearchIdeaResponse, status_code=201)
def submit_founder_idea(
    payload: AlphaFounderResearchIdeaCreate,
    db: Annotated[Session, Depends(get_db)],
):
    mandate = _locked(db, payload.mandate_id)
    item = queue_founder_idea(db, mandate, payload)
    db.commit()
    db.refresh(item)
    return _serialize_idea(item)


@router.get("/ideas", response_model=list[AlphaFounderResearchIdeaResponse])
def list_founder_ideas(db: Annotated[Session, Depends(get_db)]):
    items = db.scalars(
        select(AlphaFounderResearchIdea)
        .order_by(AlphaFounderResearchIdea.created_at.desc())
        .limit(100)
    ).all()
    return [_serialize_idea(item) for item in items]


@router.post(
    "/mandates/{mandate_id}/approve", response_model=AlphaResearchMandateResponse
)
def approve(
    mandate_id: UUID,
    payload: AlphaResearchMandateApproval,
    db: Annotated[Session, Depends(get_db)],
):
    mandate = _locked(db, mandate_id)
    approve_mandate(db, mandate, payload)
    db.commit()
    db.refresh(mandate)
    return serialize_mandate(mandate)


@router.post(
    "/mandates/{mandate_id}/reconcile", response_model=AlphaResearchMandateResponse
)
def reconcile(mandate_id: UUID, db: Annotated[Session, Depends(get_db)]):
    mandate = _locked(db, mandate_id)
    reconcile_mandate(db, mandate)
    db.commit()
    db.refresh(mandate)
    return serialize_mandate(mandate)


@router.post("/mandates/{mandate_id}/recover-grounding")
def recover_grounding(
    mandate_id: UUID,
    payload: AlphaDiscoveryGroundingRecovery,
    db: Annotated[Session, Depends(get_db)],
):
    mandate = _locked(db, mandate_id)
    cycle = recover_discovery_grounding(db, mandate, payload)
    db.commit()
    return {
        "cycle_id": str(cycle.id),
        "status": cycle.status,
        "cycle_digest": cycle.cycle_digest,
    }


@router.post("/mandates/{mandate_id}/retry-invalid-stage")
def retry_invalid_stage(
    mandate_id: UUID,
    payload: AlphaDiscoveryStageRetry,
    db: Annotated[Session, Depends(get_db)],
):
    mandate = _locked(db, mandate_id)
    cycle = retry_invalid_discovery_stage(db, mandate, payload)
    db.commit()
    db.refresh(cycle)
    return {
        "cycle_id": str(cycle.id),
        "status": cycle.status,
        "phase": cycle.phase,
        "next_action": cycle.next_action,
        "representation_task_id": (
            str(cycle.representation_task_id)
            if cycle.representation_task_id
            else None
        ),
    }


@router.get("/overview", response_model=AlphaDiscoveryOverview)
def get_overview(db: Annotated[Session, Depends(get_db)]):
    return overview(db)
