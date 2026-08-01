from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_ACTOR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSpecification(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    source_type: Literal["dataset", "paper", "observation", "prior_trial"]
    version: str = Field(min_length=1, max_length=150)
    content_sha256: str = Field(pattern=_DIGEST)
    provenance: str = Field(min_length=1, max_length=2000)
    point_in_time: bool
    observed_at: datetime | None = None


class ResearchSourceCreate(StrictModel):
    source_key: str = Field(pattern=_KEY, max_length=150)
    specification: SourceSpecification
    record_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class DataSnapshotSpecification(StrictModel):
    provider: str = Field(min_length=1, max_length=150)
    instrument: str = Field(min_length=1, max_length=150)
    timeframe: str = Field(min_length=1, max_length=100)
    date_start: datetime
    date_end: datetime
    rows: int = Field(ge=100, le=100_000_000)
    format: Literal["csv", "parquet"]
    storage_uri: str = Field(min_length=1, max_length=1000)
    transformation: str = Field(min_length=1, max_length=4000)
    point_in_time: bool

    @model_validator(mode="after")
    def snapshot_dates_are_ordered(self) -> DataSnapshotSpecification:
        if self.date_end <= self.date_start:
            raise ValueError("snapshot date_end must be after date_start")
        return self


class ResearchDataSnapshotCreate(StrictModel):
    snapshot_key: str = Field(pattern=_KEY, max_length=150)
    source_id: uuid.UUID
    specification: DataSnapshotSpecification
    content_digest: str = Field(pattern=_DIGEST)
    record_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class ResearchDataSnapshotResponse(ResearchDataSnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    registered_at: datetime


class HypothesisSpecification(StrictModel):
    research_question: str = Field(min_length=10, max_length=2000)
    rationale: str = Field(min_length=10, max_length=4000)
    mechanism: str = Field(min_length=10, max_length=4000)
    prediction: str = Field(min_length=10, max_length=2000)
    universe: list[str] = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=500)
    horizon: str = Field(min_length=1, max_length=200)
    null_hypothesis: str = Field(min_length=10, max_length=2000)
    failure_conditions: list[str] = Field(min_length=1, max_length=30)
    rival_explanations: list[str] = Field(min_length=1, max_length=30)
    maximum_trials: int = Field(ge=1, le=100)


class ResearchHypothesisCreate(StrictModel):
    hypothesis_key: str = Field(pattern=_KEY, max_length=150)
    trial_family: str = Field(pattern=_KEY, max_length=150)
    specification: HypothesisSpecification
    record_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class ExperimentManifest(StrictModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    repository_commit: str = Field(pattern=_COMMIT)
    dataset_version: str = Field(min_length=1, max_length=200)
    instrument_universe: list[str] = Field(min_length=1, max_length=100)
    timeframe: str = Field(min_length=1, max_length=100)
    date_start: date | None = None
    date_end: date | None = None
    sample_range: str | None = Field(default=None, min_length=3, max_length=300)
    features: list[str] = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=500)
    model_or_rule: str = Field(min_length=1, max_length=2000)
    parameters: dict[str, str | int | float | bool]
    fees_bps: float = Field(ge=0, le=1000)
    slippage_bps: float = Field(ge=0, le=1000)
    delay_bars: int = Field(ge=0, le=10000)
    validation_method: str = Field(min_length=3, max_length=500)
    success_criteria: list[str] = Field(min_length=1, max_length=30)
    rejection_criteria: list[str] = Field(min_length=1, max_length=30)
    engine_version: str = Field(min_length=1, max_length=150)
    data_snapshot_digest: str | None = Field(default=None, pattern=_DIGEST)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> ExperimentManifest:
        if (self.date_start is None) != (self.date_end is None):
            raise ValueError("date_start and date_end must be supplied together")
        if self.date_start is not None and self.date_end <= self.date_start:
            raise ValueError("date_end must be after date_start")
        if self.date_start is None and self.sample_range is None:
            raise ValueError("a date range or explicit sample_range is required")
        return self


class ResearchExperimentCreate(StrictModel):
    experiment_key: str = Field(pattern=_KEY, max_length=150)
    hypothesis_id: uuid.UUID
    source_id: uuid.UUID
    snapshot_id: uuid.UUID | None = None
    manifest: ExperimentManifest
    manifest_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)

    @model_validator(mode="after")
    def snapshot_is_digest_bound(self) -> ResearchExperimentCreate:
        if (self.snapshot_id is None) != (self.manifest.data_snapshot_digest is None):
            raise ValueError(
                "snapshot_id and data_snapshot_digest are required together"
            )
        return self


class ResearchReviewCreate(StrictModel):
    subject_digest: str = Field(pattern=_DIGEST)
    review_kind: Literal["approval", "independent_review", "adversarial_review"]
    verdict: Literal["approved", "rejected", "needs_changes"]
    review: dict[str, str | int | float | bool | list[str]]
    reviewer: str = Field(pattern=_ACTOR, max_length=150)


class TrialPlan(StrictModel):
    run_id: str = Field(pattern=_KEY, max_length=150)
    task_id: uuid.UUID
    code_commit: str = Field(pattern=_COMMIT)
    dataset_digest: str = Field(pattern=_DIGEST)
    engine_digest: str = Field(pattern=_DIGEST)


class ResearchTrialCreate(StrictModel):
    experiment_digest: str = Field(pattern=_DIGEST)
    plan: TrialPlan
    record_digest: str = Field(pattern=_DIGEST)
    executed_by: str = Field(pattern=_ACTOR, max_length=150)


class ResultDocument(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    metrics: dict[str, float | int | bool | None]
    robustness_status: Literal["not_tested", "failed", "partial", "passed"]
    rejection_reason: str | None = Field(default=None, max_length=2000)
    evidence_artifacts: list[str] = Field(min_length=1, max_length=50)
    output_artifact_digest: str = Field(pattern=_DIGEST)
    started_at: datetime
    ended_at: datetime

    @model_validator(mode="after")
    def times_are_ordered(self) -> ResultDocument:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        return self


class ResearchResultCreate(StrictModel):
    trial_digest: str = Field(pattern=_DIGEST)
    outcome: Literal["accepted", "rejected", "failed", "inconclusive"]
    result: ResultDocument
    record_digest: str = Field(pattern=_DIGEST)
    recorded_by: str = Field(pattern=_ACTOR, max_length=150)


class ResearchDecisionCreate(StrictModel):
    result_digest: str = Field(pattern=_DIGEST)
    decision: Literal["retain", "replicate", "reject", "retire"]
    rationale: str = Field(min_length=10, max_length=4000)
    decided_by: str = Field(pattern=_ACTOR, max_length=150)


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    record_digest: str


class ResearchSourceResponse(RecordResponse):
    source_key: str
    specification: SourceSpecification
    registered_by: str
    registered_at: datetime


class ResearchHypothesisResponse(RecordResponse):
    hypothesis_key: str
    trial_family: str
    specification: HypothesisSpecification
    registered_by: str
    registered_at: datetime


class ResearchExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    experiment_key: str
    hypothesis_id: uuid.UUID
    source_id: uuid.UUID
    snapshot_id: uuid.UUID | None
    manifest: ExperimentManifest
    manifest_digest: str
    registered_by: str
    registered_at: datetime


class ResearchReviewResponse(RecordResponse):
    subject_type: str
    subject_id: uuid.UUID
    subject_digest: str
    review_kind: str
    verdict: str
    review: dict
    reviewer: str
    reviewed_at: datetime


class ResearchTrialResponse(RecordResponse):
    experiment_id: uuid.UUID
    trial_family: str
    run_id: str
    trial_number: int
    plan: TrialPlan
    executed_by: str
    registered_at: datetime


class ResearchResultResponse(RecordResponse):
    trial_id: uuid.UUID
    outcome: str
    result: ResultDocument
    recorded_by: str
    recorded_at: datetime


class ResearchDecisionResponse(RecordResponse):
    result_id: uuid.UUID
    decision: str
    rationale: str
    result_digest: str
    decided_by: str
    decided_at: datetime


class ResearchLineageResponse(StrictModel):
    hypothesis: ResearchHypothesisResponse
    experiments: list[ResearchExperimentResponse]
    trials: list[ResearchTrialResponse]
    results: list[ResearchResultResponse]
    reviews: list[ResearchReviewResponse]
    decisions: list[ResearchDecisionResponse]
    trial_family_count: int


class ResearchDocumentCreate(StrictModel):
    document_key: str = Field(pattern=_KEY, max_length=150)
    title: str = Field(min_length=1, max_length=300)
    document_type: Literal["prd", "textbook", "paper", "prior_report", "runbook"]
    evidence_type: Literal[
        "governing_requirement",
        "method",
        "empirical_evidence",
        "prior_result",
        "operational_record",
    ]
    version: str = Field(min_length=1, max_length=150)
    source_uri: str = Field(min_length=1, max_length=1000)
    content_digest: str = Field(pattern=_DIGEST)
    metadata: dict[str, str | int | list[str]] = Field(default_factory=dict)
    ingested_by: str = Field(pattern=_ACTOR, max_length=150)


class ResearchDocumentResponse(ResearchDocumentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ingested_at: datetime


class ResearchChunkCreate(StrictModel):
    ordinal: int = Field(ge=0)
    section: str = Field(min_length=1, max_length=500)
    page: int | None = Field(default=None, ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=20000)
    text_digest: str = Field(pattern=_DIGEST)
    metadata: dict[str, str | int | list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def lines_are_ordered(self) -> ResearchChunkCreate:
        if self.line_end < self.line_start:
            raise ValueError("line_end cannot precede line_start")
        return self


class ResearchChunkResponse(ResearchChunkCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID


class ResearchDocumentBundleCreate(StrictModel):
    document: ResearchDocumentCreate
    chunks: list[ResearchChunkCreate] = Field(min_length=1, max_length=5000)


class ResearchDocumentBundleResponse(StrictModel):
    document: ResearchDocumentResponse
    chunk_count: int


class KnowledgeSearchRequest(StrictModel):
    query: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=8, ge=1, le=25)
    evidence_types: list[str] = Field(default_factory=list, max_length=10)


class KnowledgeSearchHit(StrictModel):
    chunk_id: uuid.UUID
    document_key: str
    title: str
    evidence_type: str
    section: str
    page: int | None
    line_start: int
    line_end: int
    text: str
    text_digest: str
    score: float
    citation: str


class SimilarHypothesisHit(StrictModel):
    hypothesis_id: uuid.UUID
    hypothesis_key: str
    trial_family: str
    research_question: str
    score: float
    outcomes: list[str]
    decisions: list[str]


class KnowledgeSearchResponse(StrictModel):
    query: str
    corpus_digest: str
    passages: list[KnowledgeSearchHit]
    similar_hypotheses: list[SimilarHypothesisHit]
    prior_failures: list[SimilarHypothesisHit]


class EvaluationCase(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    expected_document_keys: list[str] = Field(min_length=1, max_length=20)
    expected_terms: list[str] = Field(min_length=1, max_length=30)


class RetrievalEvaluationCreate(StrictModel):
    evaluation_key: str = Field(pattern=_KEY, max_length=150)
    cases: list[EvaluationCase] = Field(min_length=1, max_length=100)
    minimum_recall: float = Field(default=1.0, ge=0, le=1)
    evaluated_by: str = Field(pattern=_ACTOR, max_length=150)


class RetrievalEvaluationResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    evaluation_key: str
    corpus_digest: str
    question_set_digest: str
    report: dict
    passed: bool
    record_digest: str
    evaluated_by: str
    evaluated_at: datetime


class BriefClaim(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    evidence_class: Literal["source_passage", "prior_result", "agent_inference"]
    citation_chunk_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def citations_match_class(self) -> BriefClaim:
        if self.evidence_class == "agent_inference" and self.citation_chunk_ids:
            raise ValueError("agent inference cannot masquerade as a citation")
        if self.evidence_class != "agent_inference" and not self.citation_chunk_ids:
            raise ValueError("material source claims require citations")
        return self


class ResearchBriefCreate(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    summary: str = Field(min_length=1, max_length=4000)
    claims: list[BriefClaim] = Field(min_length=1, max_length=50)
    created_by: str = Field(pattern=_ACTOR, max_length=150)


class DomainProfileCreate(StrictModel):
    domain_key: str = Field(pattern=_KEY, max_length=150)
    version: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=10, max_length=4000)
    document_keys: list[str] = Field(min_length=1, max_length=200)
    required_evidence_types: list[str] = Field(min_length=1, max_length=10)
    evaluation_id: uuid.UUID
    qualified_roles: list[str] = Field(min_length=1, max_length=20)
    created_by: str = Field(pattern=_ACTOR, max_length=150)


class DomainProfileResponse(DomainProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    corpus_digest: str
    status: Literal["active"]
    record_digest: str
    created_at: datetime


class IntelligenceCandidate(StrictModel):
    question: str = Field(min_length=10, max_length=1000)
    rationale: str = Field(min_length=10, max_length=2000)
    mechanism: str = Field(min_length=3, max_length=1000)
    data_requirements: list[str] = Field(min_length=1, max_length=20)
    falsification_conditions: list[str] = Field(min_length=1, max_length=20)
    citation_chunk_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    information_value: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)


class IntelligenceRunCreate(StrictModel):
    domain_profile_id: uuid.UUID
    objective: str = Field(min_length=10, max_length=2000)
    candidates: list[IntelligenceCandidate] = Field(min_length=2, max_length=10)
    created_by: str = Field(pattern=_ACTOR, max_length=150)


class AgentIntelligenceRunCreate(StrictModel):
    domain_profile_id: uuid.UUID
    objective: str = Field(min_length=10, max_length=2000)
    candidates: list[IntelligenceCandidate] = Field(min_length=2, max_length=10)


class IntelligenceRunResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    domain_profile_id: uuid.UUID
    objective: str
    candidates: list[dict]
    selected_candidate: dict
    record_digest: str
    created_by: str
    created_at: datetime


class ResearchMemoryCounts(StrictModel):
    trades: int = Field(ge=0)
    invalid_trades: int = Field(ge=0)
    state_buckets: int = Field(ge=0)
    candidates: int = Field(ge=0)
    recommendations: int = Field(ge=0)


class ResearchMemoryState(StrictModel):
    state_key: str = Field(min_length=1, max_length=150)
    bucket: str = Field(min_length=1, max_length=150)
    setup_class: str | None = Field(default=None, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    n_trades: int = Field(ge=0)
    ev_r_net: float | None = None
    avg_cost_drag_r: float | None = None
    finding_type: str | None = Field(default=None, max_length=100)
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class ResearchMemoryCandidate(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    run_id: str | None = Field(default=None, max_length=150)
    candidate_status: str | None = Field(default=None, max_length=100)
    rank_score: float | None = None
    promotion_score: float | None = None
    ev_r_net: float | None = None
    n_trades: int | None = Field(default=None, ge=0)
    recommended_action: str | None = Field(default=None, max_length=2000)


class ResearchMemoryRecommendation(StrictModel):
    recommendation_type: str = Field(min_length=1, max_length=100)
    target_type: str = Field(min_length=1, max_length=100)
    target_id: str | None = Field(default=None, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    setup_class: str | None = Field(default=None, max_length=150)
    recommendation: str = Field(min_length=1, max_length=4000)
    evidence_score: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str = Field(min_length=1, max_length=100)
    human_approved: bool


class ResearchMemoryExportDocument(StrictModel):
    schema_version: Literal[1]
    repository: Literal["bulletproof_bt"]
    repository_commit: str = Field(pattern=_COMMIT)
    database_digest: str = Field(pattern=_DIGEST)
    counts: ResearchMemoryCounts
    run_ids: list[str] = Field(default_factory=list, max_length=500)
    hypothesis_ids: list[str] = Field(default_factory=list, max_length=500)
    strongest_states: list[ResearchMemoryState] = Field(
        default_factory=list, max_length=100
    )
    weakest_states: list[ResearchMemoryState] = Field(
        default_factory=list, max_length=100
    )
    candidates: list[ResearchMemoryCandidate] = Field(
        default_factory=list, max_length=100
    )
    recommendations: list[ResearchMemoryRecommendation] = Field(
        default_factory=list, max_length=100
    )


class ResearchMemoryExportCreate(StrictModel):
    export: ResearchMemoryExportDocument
    export_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class AgentResearchMemoryExportCreate(StrictModel):
    export: ResearchMemoryExportDocument
    export_digest: str = Field(pattern=_DIGEST)
    summary: str = Field(min_length=1, max_length=19000)
    summary_digest: str = Field(pattern=_DIGEST)


class ResearchMemoryExportResponse(ResearchMemoryExportCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    repository: str
    repository_commit: str
    database_digest: str
    registered_at: datetime


class ResearchMemorySyncResponse(StrictModel):
    export: ResearchMemoryExportResponse
    document_key: str
    unchanged: bool


class AgentResearchBriefCreate(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    summary: str = Field(min_length=1, max_length=4000)
    claims: list[BriefClaim] = Field(min_length=1, max_length=50)


class AgentResearchHypothesisCreate(StrictModel):
    hypothesis_key: str = Field(pattern=_KEY, max_length=150)
    trial_family: str = Field(pattern=_KEY, max_length=150)
    specification: HypothesisSpecification
    record_digest: str = Field(pattern=_DIGEST)


class AgentResearchExperimentCreate(StrictModel):
    experiment_key: str = Field(pattern=_KEY, max_length=150)
    hypothesis_id: uuid.UUID
    source_id: uuid.UUID
    snapshot_id: uuid.UUID
    manifest: ExperimentManifest
    manifest_digest: str = Field(pattern=_DIGEST)


class AgentResearchReviewCreate(StrictModel):
    subject_digest: str = Field(pattern=_DIGEST)
    verdict: Literal["approved", "rejected", "needs_changes"]
    review: dict[str, str | int | float | bool | list[str]]


class AgentResearchResultCreate(StrictModel):
    trial_digest: str = Field(pattern=_DIGEST)
    outcome: Literal["accepted", "rejected", "failed", "inconclusive"]
    result: ResultDocument
    record_digest: str = Field(pattern=_DIGEST)


class ResearchBriefResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    question: str
    corpus_digest: str
    evaluation_id: uuid.UUID
    brief: dict
    record_digest: str
    created_by: str
    created_at: datetime
