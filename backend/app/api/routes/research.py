from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import (
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchReview,
    ResearchTrial,
)
from app.schemas.research import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ResearchBriefCreate,
    ResearchBriefResponse,
    ResearchChunkCreate,
    ResearchChunkResponse,
    ResearchDecisionCreate,
    ResearchDecisionResponse,
    ResearchDocumentCreate,
    ResearchDocumentResponse,
    ResearchExperimentCreate,
    ResearchExperimentResponse,
    ResearchHypothesisCreate,
    ResearchHypothesisResponse,
    ResearchLineageResponse,
    ResearchResultCreate,
    ResearchResultResponse,
    ResearchReviewCreate,
    ResearchReviewResponse,
    ResearchSourceCreate,
    ResearchSourceResponse,
    ResearchTrialCreate,
    ResearchTrialResponse,
    RetrievalEvaluationCreate,
    RetrievalEvaluationResponse,
)
from app.services.research import (
    add_review,
    create_brief,
    evaluate_retrieval,
    register_chunk,
    register_decision,
    register_document,
    register_experiment,
    register_hypothesis,
    register_result,
    register_source,
    register_trial,
    search_knowledge,
)

router = APIRouter(
    prefix="/v1/research",
    tags=["research-registry"],
    dependencies=[Depends(require_orchestrator)],
)


def _document_response(record) -> ResearchDocumentResponse:
    return ResearchDocumentResponse(
        id=record.id,
        document_key=record.document_key,
        title=record.title,
        document_type=record.document_type,
        evidence_type=record.evidence_type,
        version=record.version,
        source_uri=record.source_uri,
        content_digest=record.content_digest,
        metadata=record.metadata_,
        ingested_by=record.ingested_by,
        ingested_at=record.ingested_at,
    )


def _chunk_response(record) -> ResearchChunkResponse:
    return ResearchChunkResponse(
        id=record.id,
        document_id=record.document_id,
        ordinal=record.ordinal,
        section=record.section,
        page=record.page,
        line_start=record.line_start,
        line_end=record.line_end,
        text=record.text,
        text_digest=record.text_digest,
        metadata=record.metadata_,
    )


@router.post(
    "/knowledge/documents", response_model=ResearchDocumentResponse, status_code=201
)
def create_document(
    payload: ResearchDocumentCreate, db: Annotated[Session, Depends(get_db)]
):
    return _document_response(register_document(db, payload))


@router.post(
    "/knowledge/documents/{document_id}/chunks",
    response_model=ResearchChunkResponse,
    status_code=201,
)
def create_chunk(
    document_id: UUID,
    payload: ResearchChunkCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return _chunk_response(register_chunk(db, document_id, payload))


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    payload: KnowledgeSearchRequest, db: Annotated[Session, Depends(get_db)]
):
    return KnowledgeSearchResponse.model_validate(
        search_knowledge(db, payload.query, payload.limit, payload.evidence_types)
    )


@router.post(
    "/knowledge/evaluations",
    response_model=RetrievalEvaluationResponse,
    status_code=201,
)
def create_evaluation(
    payload: RetrievalEvaluationCreate, db: Annotated[Session, Depends(get_db)]
):
    return RetrievalEvaluationResponse.model_validate(evaluate_retrieval(db, payload))


@router.post("/knowledge/briefs", response_model=ResearchBriefResponse, status_code=201)
def create_research_brief(
    payload: ResearchBriefCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchBriefResponse.model_validate(create_brief(db, payload))


@router.post("/sources", response_model=ResearchSourceResponse, status_code=201)
def create_source(
    payload: ResearchSourceCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchSourceResponse.model_validate(register_source(db, payload))


@router.post("/hypotheses", response_model=ResearchHypothesisResponse, status_code=201)
def create_hypothesis(
    payload: ResearchHypothesisCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchHypothesisResponse.model_validate(register_hypothesis(db, payload))


@router.post("/experiments", response_model=ResearchExperimentResponse, status_code=201)
def create_experiment(
    payload: ResearchExperimentCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchExperimentResponse.model_validate(register_experiment(db, payload))


@router.post(
    "/{subject_type}/{subject_id}/reviews",
    response_model=ResearchReviewResponse,
    status_code=201,
)
def create_review(
    subject_type: Literal["hypothesis", "experiment", "result"],
    subject_id: UUID,
    payload: ResearchReviewCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ResearchReviewResponse.model_validate(
        add_review(db, subject_type, subject_id, payload)
    )


@router.post(
    "/experiments/{experiment_id}/trials",
    response_model=ResearchTrialResponse,
    status_code=201,
)
def create_trial(
    experiment_id: UUID,
    payload: ResearchTrialCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ResearchTrialResponse.model_validate(
        register_trial(db, experiment_id, payload)
    )


@router.post(
    "/trials/{trial_id}/results", response_model=ResearchResultResponse, status_code=201
)
def create_result(
    trial_id: UUID,
    payload: ResearchResultCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ResearchResultResponse.model_validate(register_result(db, trial_id, payload))


@router.post(
    "/results/{result_id}/decisions",
    response_model=ResearchDecisionResponse,
    status_code=201,
)
def create_decision(
    result_id: UUID,
    payload: ResearchDecisionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ResearchDecisionResponse.model_validate(
        register_decision(db, result_id, payload)
    )


@router.get("/hypotheses", response_model=list[ResearchHypothesisResponse])
def list_hypotheses(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchHypothesis).order_by(ResearchHypothesis.registered_at.desc())
    ).all()
    return [ResearchHypothesisResponse.model_validate(record) for record in records]


@router.get(
    "/hypotheses/{hypothesis_id}/lineage", response_model=ResearchLineageResponse
)
def get_lineage(hypothesis_id: UUID, db: Annotated[Session, Depends(get_db)]):
    hypothesis = db.get(ResearchHypothesis, hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found.")
    experiments = db.scalars(
        select(ResearchExperiment).where(
            ResearchExperiment.hypothesis_id == hypothesis.id
        )
    ).all()
    experiment_ids = [item.id for item in experiments]
    trials = (
        db.scalars(
            select(ResearchTrial).where(ResearchTrial.experiment_id.in_(experiment_ids))
        ).all()
        if experiment_ids
        else []
    )
    trial_ids = [item.id for item in trials]
    results = (
        db.scalars(
            select(ResearchResult).where(ResearchResult.trial_id.in_(trial_ids))
        ).all()
        if trial_ids
        else []
    )
    result_ids = [item.id for item in results]
    subject_ids = [hypothesis.id, *experiment_ids, *result_ids]
    reviews = db.scalars(
        select(ResearchReview).where(ResearchReview.subject_id.in_(subject_ids))
    ).all()
    decisions = (
        db.scalars(
            select(ResearchDecision).where(ResearchDecision.result_id.in_(result_ids))
        ).all()
        if result_ids
        else []
    )
    family_count = (
        db.scalar(
            select(func.count(ResearchTrial.id)).where(
                ResearchTrial.trial_family == hypothesis.trial_family
            )
        )
        or 0
    )
    return ResearchLineageResponse(
        hypothesis=ResearchHypothesisResponse.model_validate(hypothesis),
        experiments=[
            ResearchExperimentResponse.model_validate(item) for item in experiments
        ],
        trials=[ResearchTrialResponse.model_validate(item) for item in trials],
        results=[ResearchResultResponse.model_validate(item) for item in results],
        reviews=[ResearchReviewResponse.model_validate(item) for item in reviews],
        decisions=[ResearchDecisionResponse.model_validate(item) for item in decisions],
        trial_family_count=family_count,
    )
