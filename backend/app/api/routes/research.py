from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import (
    Agent,
    FounderProposal,
    ResearchBrief,
    ResearchChunk,
    ResearchDecision,
    ResearchDocument,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchMemoryExport,
    ResearchResult,
    ResearchRetrievalEvaluation,
    ResearchReview,
    ResearchTrial,
    Task,
)
from app.schemas import FounderProposalDocument, FounderProposalResponse, TaskCreate
from app.schemas.research import (
    DomainProfileCreate,
    DomainProfileResponse,
    IntelligenceRunCreate,
    IntelligenceRunResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ResearchBriefCreate,
    ResearchBriefResponse,
    ResearchChunkCreate,
    ResearchChunkResponse,
    ResearchDataSnapshotCreate,
    ResearchDataSnapshotResponse,
    ResearchDecisionCreate,
    ResearchDecisionResponse,
    ResearchDocumentBundleCreate,
    ResearchDocumentBundleResponse,
    ResearchDocumentCreate,
    ResearchDocumentResponse,
    ResearchExperimentCreate,
    ResearchExperimentResponse,
    ResearchHypothesisCreate,
    ResearchHypothesisResponse,
    ResearchLineageResponse,
    ResearchMemoryExportCreate,
    ResearchMemoryExportResponse,
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
from app.services.proposals import create_proposal
from app.services.research import (
    add_review,
    create_brief,
    evaluate_retrieval,
    register_chunk,
    register_data_snapshot,
    register_decision,
    register_document,
    register_document_bundle,
    register_domain_profile,
    register_experiment,
    register_hypothesis,
    register_intelligence_run,
    register_memory_export,
    register_result,
    register_source,
    register_trial,
    search_knowledge,
)
from app.services.tasks import append_task_event, build_task

router = APIRouter(
    prefix="/v1/research",
    tags=["research-registry"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/domains", response_model=DomainProfileResponse, status_code=201)
def create_domain_profile(
    payload: DomainProfileCreate, db: Annotated[Session, Depends(get_db)]
):
    record = register_domain_profile(db, payload)
    return DomainProfileResponse(
        id=record.id,
        domain_key=record.domain_key,
        version=record.version,
        title=record.title,
        description=record.specification["description"],
        document_keys=record.specification["document_keys"],
        required_evidence_types=record.specification["required_evidence_types"],
        evaluation_id=record.evaluation_id,
        qualified_roles=record.specification["qualified_roles"],
        created_by=record.created_by,
        corpus_digest=record.corpus_digest,
        status=record.status,
        record_digest=record.record_digest,
        created_at=record.created_at,
    )


@router.get("/domains", response_model=list[DomainProfileResponse])
def list_domain_profiles(db: Annotated[Session, Depends(get_db)]):
    from app.models import ResearchDomainProfile

    records = db.scalars(
        select(ResearchDomainProfile).order_by(ResearchDomainProfile.created_at.desc())
    ).all()
    return [
        DomainProfileResponse(
            id=item.id,
            domain_key=item.domain_key,
            version=item.version,
            title=item.title,
            description=item.specification["description"],
            document_keys=item.specification["document_keys"],
            required_evidence_types=item.specification["required_evidence_types"],
            evaluation_id=item.evaluation_id,
            qualified_roles=item.specification["qualified_roles"],
            created_by=item.created_by,
            corpus_digest=item.corpus_digest,
            status=item.status,
            record_digest=item.record_digest,
            created_at=item.created_at,
        )
        for item in records
    ]


@router.post(
    "/intelligence/runs", response_model=IntelligenceRunResponse, status_code=201
)
def create_intelligence_run(
    payload: IntelligenceRunCreate, db: Annotated[Session, Depends(get_db)]
):
    return IntelligenceRunResponse.model_validate(
        register_intelligence_run(db, payload)
    )


@router.get("/intelligence/runs", response_model=list[IntelligenceRunResponse])
def list_intelligence_runs(db: Annotated[Session, Depends(get_db)]):
    from app.models import ResearchIntelligenceRun

    return [
        IntelligenceRunResponse.model_validate(item)
        for item in db.scalars(
            select(ResearchIntelligenceRun).order_by(
                ResearchIntelligenceRun.created_at.desc()
            )
        ).all()
    ]


@router.post(
    "/memory-exports", response_model=ResearchMemoryExportResponse, status_code=201
)
def create_memory_export(
    payload: ResearchMemoryExportCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchMemoryExportResponse.model_validate(
        register_memory_export(db, payload)
    )


@router.get(
    "/memory-exports/by-digest/{export_digest}",
    response_model=ResearchMemoryExportResponse,
)
def get_memory_export_by_digest(
    export_digest: str, db: Annotated[Session, Depends(get_db)]
):
    record = db.scalar(
        select(ResearchMemoryExport).where(
            ResearchMemoryExport.export_digest == export_digest
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Research-memory export not found.")
    return ResearchMemoryExportResponse.model_validate(record)


@router.get("/memory-exports", response_model=list[ResearchMemoryExportResponse])
def list_memory_exports(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchMemoryExport)
        .order_by(ResearchMemoryExport.registered_at.desc())
        .limit(25)
    ).all()
    return [ResearchMemoryExportResponse.model_validate(item) for item in records]


@router.post(
    "/memory-sync/proposals", response_model=FounderProposalResponse, status_code=201
)
def propose_memory_sync(db: Annotated[Session, Depends(get_db)]):
    active_task = db.scalar(
        select(Task).where(
            Task.task_type == "research_memory_sync",
            Task.status.in_({"queued", "leased", "running", "pending_approval"}),
        )
    )
    if active_task is not None:
        raise HTTPException(
            status_code=409,
            detail="A research-memory synchronization task is already active.",
        )
    proposed = db.scalars(
        select(FounderProposal).where(FounderProposal.status == "proposed")
    ).all()
    for item in proposed:
        task = item.proposal.get("proposed_task") or {}
        if task.get("task_type") == "research_memory_sync":
            raise HTTPException(
                status_code=409,
                detail="A research-memory synchronization proposal is pending.",
            )
    planners = db.scalars(
        select(Agent).where(Agent.is_enabled.is_(True)).order_by(Agent.created_at)
    ).all()
    planner = next(
        (agent for agent in planners if "founder-intake" in agent.capabilities), None
    )
    if planner is None:
        raise HTTPException(status_code=409, detail="Founder planner is unavailable.")
    now = datetime.now(UTC)
    source = build_task(
        TaskCreate(
            task_number=f"MEMORY-SYNC-REQUEST-{now:%Y%m%dT%H%M%S%fZ}",
            project="bulletproof_bt",
            task_type="founder_request",
            title="Synchronize Bulletproof research memory",
            objective=(
                "Create a governed proposal for one read-only, digest-bound "
                "Bulletproof research-memory synchronization."
            ),
            priority=60,
            risk_level=0,
            created_by="founder-mission-control",
            input_contract={"schema_version": 1, "request_kind": "task"},
            expected_outputs=["reviewable memory synchronization proposal"],
            acceptance_criteria=["No primary checkout or research database is modified."],
            approval_policy={"kind": "proposal_review", "risk": 0},
            approval_required=False,
            required_capabilities=[],
            allowed_machines=["vm1-developer"],
            max_attempts=1,
        )
    )
    source.status = "succeeded"
    source.completed_at = now
    db.add(source)
    db.flush()
    append_task_event(
        db,
        source,
        "task_created",
        "Founder requested a bounded research-memory synchronization proposal.",
        payload={"created_by": "founder-mission-control", "risk_level": 0},
    )
    document = FounderProposalDocument.model_validate(
        {
            "schema_version": 1,
            "summary": "Synchronize Bulletproof research memory into Hermes.",
            "interpretation": (
                "Read the fixed VM1 Bulletproof research-memory database, create a "
                "bounded digest-bound projection, and register it with Hermes."
            ),
            "recommended_action": "create_task",
            "assumptions": ["The VM1 Bulletproof memory database is available."],
            "clarification_questions": [],
            "target_role": "VM1 Research Memory Steward",
            "target_role_reason": (
                "This dedicated read-only role is colocated with the authoritative "
                "Bulletproof database on VM1."
            ),
            "safety_constraints": [
                "Read-only database access.",
                "No primary-checkout writes.",
                "No arbitrary task paths or commands.",
            ],
            "proposed_task": {
                "project": "bulletproof_bt",
                "task_type": "research_memory_sync",
                "title": "Sync Bulletproof research memory",
                "objective": (
                    "Register one current, bounded and digest-bound Bulletproof "
                    "research-memory export in Hermes."
                ),
                "priority": 60,
                "risk_level": 0,
                "input_contract": {
                    "repository": "bulletproof_bt",
                    "workflow": "research-memory-sync",
                    "base_ref": "main",
                },
                "expected_outputs": [
                    "structured memory export",
                    "searchable bounded summary",
                ],
                "acceptance_criteria": [
                    "Export and summary digests are verified by the control plane.",
                    "The source database and primary checkout remain unchanged.",
                ],
                "approval_policy": {"kind": "proposal_review", "risk": 0},
                "approval_required": False,
                "required_capabilities": [
                    "git",
                    "python",
                    "research-memory-sync",
                ],
                "allowed_machines": ["vm1-developer"],
                "max_attempts": 1,
            },
        }
    )
    proposal = create_proposal(
        db, source_task=source, planner=planner, document=document
    )
    db.commit()
    db.refresh(proposal)
    return FounderProposalResponse.model_validate(proposal)


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
    "/knowledge/document-bundles",
    response_model=ResearchDocumentBundleResponse,
    status_code=201,
)
def create_document_bundle(
    payload: ResearchDocumentBundleCreate, db: Annotated[Session, Depends(get_db)]
):
    record = register_document_bundle(db, payload)
    return ResearchDocumentBundleResponse(
        document=_document_response(record), chunk_count=len(payload.chunks)
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


@router.get(
    "/knowledge/documents/by-key/{document_key}",
    response_model=ResearchDocumentResponse,
)
def get_document_by_key(document_key: str, db: Annotated[Session, Depends(get_db)]):
    record = db.scalar(
        select(ResearchDocument).where(ResearchDocument.document_key == document_key)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_response(record)


@router.get(
    "/knowledge/documents/by-digest/{content_digest}",
    response_model=ResearchDocumentResponse,
)
def get_document_by_digest(
    content_digest: str, db: Annotated[Session, Depends(get_db)]
):
    record = db.scalar(
        select(ResearchDocument).where(
            ResearchDocument.content_digest == content_digest
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_response(record)


@router.get(
    "/knowledge/documents/{document_id}/chunks",
    response_model=list[ResearchChunkResponse],
)
def list_document_chunks(document_id: UUID, db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchChunk)
        .where(ResearchChunk.document_id == document_id)
        .order_by(ResearchChunk.ordinal)
    ).all()
    return [_chunk_response(record) for record in records]


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


@router.get(
    "/knowledge/evaluations/by-key/{evaluation_key}",
    response_model=RetrievalEvaluationResponse,
)
def get_evaluation_by_key(evaluation_key: str, db: Annotated[Session, Depends(get_db)]):
    record = db.scalar(
        select(ResearchRetrievalEvaluation).where(
            ResearchRetrievalEvaluation.evaluation_key == evaluation_key
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return RetrievalEvaluationResponse.model_validate(record)


@router.post("/knowledge/briefs", response_model=ResearchBriefResponse, status_code=201)
def create_research_brief(
    payload: ResearchBriefCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchBriefResponse.model_validate(create_brief(db, payload))


@router.get(
    "/knowledge/briefs/by-digest/{record_digest}",
    response_model=ResearchBriefResponse,
)
def get_brief_by_digest(record_digest: str, db: Annotated[Session, Depends(get_db)]):
    record = db.scalar(
        select(ResearchBrief).where(ResearchBrief.record_digest == record_digest)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Brief not found.")
    return ResearchBriefResponse.model_validate(record)


@router.post("/sources", response_model=ResearchSourceResponse, status_code=201)
def create_source(
    payload: ResearchSourceCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchSourceResponse.model_validate(register_source(db, payload))


@router.post(
    "/data-snapshots",
    response_model=ResearchDataSnapshotResponse,
    status_code=201,
)
def create_data_snapshot(
    payload: ResearchDataSnapshotCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ResearchDataSnapshotResponse.model_validate(
        register_data_snapshot(db, payload)
    )


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
