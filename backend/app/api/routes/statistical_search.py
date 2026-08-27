from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.statistical_search import (
    StatisticalSearchCampaign,
    StatisticalSearchEvent,
)
from app.schemas.statistical_search import (
    SearchCancellation,
    SearchObservationBatch,
    SearchProposalResponse,
    StatisticalSearchCreate,
    StatisticalSearchResponse,
)
from app.services.statistical_search import (
    StatisticalSearchConflict,
    cancel,
    observe,
    propose,
    register_campaign,
    verify_event_chain,
)

router = APIRouter(
    prefix="/v1/research/statistical-searches",
    tags=["research-statistical-search"],
    dependencies=[Depends(require_orchestrator)],
)


def _conflict(exc):
    raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("", response_model=StatisticalSearchResponse, status_code=201)
def create_campaign(
    payload: StatisticalSearchCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_campaign(db, payload)
        db.commit()
        db.refresh(record)
        return StatisticalSearchResponse.model_validate(record)
    except StatisticalSearchConflict as exc:
        db.rollback()
        _conflict(exc)


@router.get("", response_model=list[StatisticalSearchResponse])
def list_campaigns(db: Annotated[Session, Depends(get_db)]):
    return [
        StatisticalSearchResponse.model_validate(item)
        for item in db.scalars(
            select(StatisticalSearchCampaign).order_by(
                StatisticalSearchCampaign.registered_at.desc()
            )
        ).all()
    ]


@router.get("/{campaign_id}", response_model=StatisticalSearchResponse)
def get_campaign(campaign_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(StatisticalSearchCampaign, campaign_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Search campaign not found.")
    return StatisticalSearchResponse.model_validate(record)


@router.get("/{campaign_id}/events")
def list_events(campaign_id: UUID, db: Annotated[Session, Depends(get_db)]):
    campaign = db.get(StatisticalSearchCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Search campaign not found.")
    events = list(
        db.scalars(
            select(StatisticalSearchEvent)
            .where(StatisticalSearchEvent.campaign_id == campaign_id)
            .order_by(StatisticalSearchEvent.sequence)
        ).all()
    )
    records = [
        {
            "sequence": item.sequence,
            "event_type": item.event_type,
            "detail": item.detail,
            "prior_digest": item.prior_digest,
            "record_digest": item.record_digest,
            "created_at": item.created_at,
        }
        for item in events
    ]
    return {
        "campaign_id": campaign.id,
        "valid": verify_event_chain(campaign, events),
        "head_digest": campaign.event_head_digest,
        "events": records,
    }


@router.post("/{campaign_id}/proposals", response_model=SearchProposalResponse)
def create_proposal(campaign_id: UUID, db: Annotated[Session, Depends(get_db)]):
    try:
        campaign, event, detail = propose(db, campaign_id)
        db.commit()
        return SearchProposalResponse(
            campaign_id=campaign.id,
            method=campaign.method,
            event_digest=event.record_digest,
            **detail,
        )
    except StatisticalSearchConflict as exc:
        db.rollback()
        _conflict(exc)


@router.post("/{campaign_id}/observations", response_model=StatisticalSearchResponse)
def record_observations(
    campaign_id: UUID,
    payload: SearchObservationBatch,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        campaign = observe(db, campaign_id, payload)
        db.commit()
        db.refresh(campaign)
        return StatisticalSearchResponse.model_validate(campaign)
    except StatisticalSearchConflict as exc:
        db.rollback()
        _conflict(exc)


@router.post("/{campaign_id}/cancel", response_model=StatisticalSearchResponse)
def cancel_campaign(
    campaign_id: UUID,
    payload: SearchCancellation,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        campaign = cancel(db, campaign_id, payload.actor, payload.reason)
        db.commit()
        db.refresh(campaign)
        return StatisticalSearchResponse.model_validate(campaign)
    except StatisticalSearchConflict as exc:
        db.rollback()
        _conflict(exc)
