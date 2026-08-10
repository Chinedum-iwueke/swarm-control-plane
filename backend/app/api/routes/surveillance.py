from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.surveillance import (
    SurveillanceDigest,
    SurveillancePublication,
    SurveillanceSource,
)
from app.schemas.surveillance import (
    CandidateDispositionCreate,
    CandidateDispositionResponse,
    FetchReceiptResponse,
    SourcePollCreate,
    SurveillancePublicationResponse,
    SurveillanceSourceCreate,
    SurveillanceSourceResponse,
    WeeklyDigestCreate,
    WeeklyDigestResponse,
)
from app.services.surveillance import (
    create_weekly_digest,
    dispose_candidate,
    poll_source,
    register_source,
    replay_publication,
)

router = APIRouter(
    prefix="/v1/research/surveillance",
    tags=["scientific-surveillance"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/sources", response_model=SurveillanceSourceResponse, status_code=201)
def create_source(
    payload: SurveillanceSourceCreate, db: Annotated[Session, Depends(get_db)]
):
    return register_source(db, payload)


@router.get("/sources", response_model=list[SurveillanceSourceResponse])
def list_sources(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(SurveillanceSource)
            .where(SurveillanceSource.project == "systematic-research")
            .order_by(SurveillanceSource.source_key)
        ).all()
    )


@router.post(
    "/sources/{source_id}/poll", response_model=FetchReceiptResponse, status_code=201
)
def poll(
    source_id: UUID, payload: SourcePollCreate, db: Annotated[Session, Depends(get_db)]
):
    return poll_source(db, source_id, payload)


@router.get("/candidates", response_model=list[SurveillancePublicationResponse])
def candidates(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return list(
        db.scalars(
            select(SurveillancePublication)
            .where(SurveillancePublication.project == "systematic-research")
            .order_by(SurveillancePublication.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.get("/candidates/{publication_id}/replay")
def replay(publication_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return replay_publication(db, publication_id)


@router.post(
    "/candidates/{publication_id}/disposition",
    response_model=CandidateDispositionResponse,
)
def disposition(
    publication_id: UUID,
    payload: CandidateDispositionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return dispose_candidate(db, publication_id, payload)


@router.post("/digests", response_model=WeeklyDigestResponse, status_code=201)
def digest(payload: WeeklyDigestCreate, db: Annotated[Session, Depends(get_db)]):
    return create_weekly_digest(db, payload)


@router.get("/digests", response_model=list[WeeklyDigestResponse])
def digests(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(SurveillanceDigest)
            .order_by(SurveillanceDigest.week_ending.desc())
            .limit(52)
        ).all()
    )
