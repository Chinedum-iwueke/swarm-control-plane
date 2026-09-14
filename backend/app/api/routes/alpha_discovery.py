from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.alpha_discovery import AlphaResearchMandate
from app.schemas.alpha_discovery import (
    AlphaDiscoveryOverview,
    AlphaResearchMandateApproval,
    AlphaResearchMandateCreate,
    AlphaResearchMandateResponse,
)
from app.services.alpha_discovery import (
    approve_mandate,
    overview,
    reconcile_mandate,
    register_mandate,
    serialize_mandate,
)

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


@router.get("/overview", response_model=AlphaDiscoveryOverview)
def get_overview(db: Annotated[Session, Depends(get_db)]):
    return overview(db)
