from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.memory import EvidenceOppositionRecord
from app.schemas.evidence import EvidenceObjectResponse
from app.schemas.memory import (
    BeliefLedgerCreate,
    DossierCompileCreate,
    DossierReplayResponse,
    DossierResponse,
    EpisodePublishCreate,
    OppositionCreate,
    OppositionResponse,
    OppositionReviewCreate,
    OutcomeCreate,
    OutcomeResponse,
    OutcomeSearchResponse,
)
from app.services.evidence import ORCHESTRATOR_ACCESS, evidence_response
from app.services.memory import (
    compile_dossier,
    create_opposition,
    get_dossier,
    list_dossiers,
    publish_belief,
    publish_episode,
    record_outcome,
    replay_dossier,
    review_opposition,
    search_outcomes,
)

router = APIRouter(
    prefix="/v1/research/memory",
    tags=["institutional-memory"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/oppositions", response_model=OppositionResponse, status_code=201)
def register_opposition(
    payload: OppositionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return create_opposition(db, payload, ORCHESTRATOR_ACCESS)


@router.get("/oppositions", response_model=list[OppositionResponse])
def read_oppositions(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(EvidenceOppositionRecord).order_by(
            EvidenceOppositionRecord.created_at.desc()
        )
    ).all()
    return [OppositionResponse.model_validate(item) for item in records]


@router.post(
    "/oppositions/{opposition_id}/review",
    response_model=OppositionResponse,
    status_code=201,
)
def register_opposition_review(
    opposition_id: UUID,
    payload: OppositionReviewCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return review_opposition(db, opposition_id, payload, ORCHESTRATOR_ACCESS)


@router.post("/outcomes", response_model=OutcomeResponse, status_code=201)
def register_outcome(
    payload: OutcomeCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return record_outcome(db, payload, ORCHESTRATOR_ACCESS)


@router.get("/outcomes/search", response_model=OutcomeSearchResponse)
def retrieve_outcomes(
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[str, Query(min_length=2, max_length=1000)],
    project: Annotated[str, Query(pattern=r"^[a-z][a-z0-9._-]{0,99}$")],
):
    return search_outcomes(db, query, project, ORCHESTRATOR_ACCESS)


@router.post("/beliefs", response_model=EvidenceObjectResponse, status_code=201)
def register_belief(
    payload: BeliefLedgerCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return evidence_response(publish_belief(db, payload, ORCHESTRATOR_ACCESS))


@router.post("/episodes", response_model=EvidenceObjectResponse, status_code=201)
def register_episode(
    payload: EpisodePublishCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return evidence_response(publish_episode(db, payload, ORCHESTRATOR_ACCESS))


@router.post("/dossiers", response_model=DossierResponse, status_code=201)
def register_dossier(
    payload: DossierCompileCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return compile_dossier(db, payload, ORCHESTRATOR_ACCESS)


@router.get("/dossiers", response_model=list[DossierResponse])
def read_dossiers(db: Annotated[Session, Depends(get_db)]):
    return list_dossiers(db, ORCHESTRATOR_ACCESS)


@router.get("/dossiers/{dossier_id}", response_model=DossierResponse)
def read_dossier(
    dossier_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    return get_dossier(db, dossier_id, ORCHESTRATOR_ACCESS)


@router.get("/dossiers/{dossier_id}/replay", response_model=DossierReplayResponse)
def replay_frozen_dossier(
    dossier_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    dossier, exact, impacts = replay_dossier(db, dossier_id, ORCHESTRATOR_ACCESS)
    return DossierReplayResponse(
        dossier=DossierResponse.model_validate(dossier),
        exact_replay=exact,
        impacts=impacts,
    )
