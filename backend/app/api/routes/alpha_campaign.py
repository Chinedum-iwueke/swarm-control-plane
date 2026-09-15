from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.alpha_campaign import AlphaCampaign
from app.schemas.alpha_campaign import (
    AlphaCampaignAction,
    AlphaCampaignActivation,
    AlphaCampaignAttemptCreate,
    AlphaCampaignCreate,
    AlphaCampaignResponse,
)
from app.services.alpha_campaign import (
    activate_campaign,
    cancel_campaign,
    reconcile_campaign,
    record_attempt,
    register_campaign,
    resume_campaign,
    serialize_campaign,
)

router = APIRouter(
    prefix="/v1/research/alpha-campaigns",
    tags=["real-data-alpha-campaigns"],
    dependencies=[Depends(require_orchestrator)],
)


def _locked(db: Session, campaign_id: UUID) -> AlphaCampaign:
    campaign = db.scalar(
        select(AlphaCampaign).where(AlphaCampaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise HTTPException(404, "Alpha campaign not found.")
    return campaign


@router.post(
    "", response_model=AlphaCampaignResponse, status_code=status.HTTP_201_CREATED
)
def create(payload: AlphaCampaignCreate, db: Annotated[Session, Depends(get_db)]):
    campaign = register_campaign(db, payload)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)


@router.get("", response_model=list[AlphaCampaignResponse])
def list_campaigns(
    db: Annotated[Session, Depends(get_db)],
    campaign_status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    statement = select(AlphaCampaign)
    if campaign_status:
        statement = statement.where(AlphaCampaign.status == campaign_status)
    campaigns = db.scalars(
        statement.order_by(AlphaCampaign.created_at.desc()).limit(limit)
    ).all()
    return [serialize_campaign(db, item) for item in campaigns]


@router.get("/backtests/activity")
def backtest_activity(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    category: Literal["all", "waiting", "running", "finished"] = "all",
    tier: Literal["all", "Tier2A", "Tier2B", "Tier3"] = "all",
):
    from app.services.backtest_activity import overview

    return overview(db, limit, offset, category, tier)


@router.get("/{campaign_id}", response_model=AlphaCampaignResponse)
def get(campaign_id: UUID, db: Annotated[Session, Depends(get_db)]):
    campaign = db.get(AlphaCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "Alpha campaign not found.")
    return serialize_campaign(db, campaign)


@router.post("/{campaign_id}/activate", response_model=AlphaCampaignResponse)
def activate(
    campaign_id: UUID,
    payload: AlphaCampaignActivation,
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _locked(db, campaign_id)
    activate_campaign(db, campaign, payload)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)


@router.post("/{campaign_id}/attempts", response_model=AlphaCampaignResponse)
def retain_attempt(
    campaign_id: UUID,
    payload: AlphaCampaignAttemptCreate,
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _locked(db, campaign_id)
    record_attempt(db, campaign, payload)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)


@router.post("/{campaign_id}/reconcile", response_model=AlphaCampaignResponse)
def reconcile(campaign_id: UUID, db: Annotated[Session, Depends(get_db)]):
    campaign = _locked(db, campaign_id)
    reconcile_campaign(db, campaign)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)


@router.post("/{campaign_id}/resume", response_model=AlphaCampaignResponse)
def resume(
    campaign_id: UUID,
    payload: AlphaCampaignAction,
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _locked(db, campaign_id)
    resume_campaign(db, campaign, payload)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)


@router.post("/{campaign_id}/cancel", response_model=AlphaCampaignResponse)
def cancel(
    campaign_id: UUID,
    payload: AlphaCampaignAction,
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _locked(db, campaign_id)
    cancel_campaign(db, campaign, payload)
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(db, campaign)
