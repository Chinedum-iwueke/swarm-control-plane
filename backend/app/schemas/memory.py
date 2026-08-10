from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_NAME = r"^[a-z][a-z0-9._-]{0,99}$"
_KEY = r"^[A-Z0-9][A-Z0-9._-]{1,149}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComparabilityScope(StrictModel):
    population: str = Field(min_length=1, max_length=1000)
    horizon: str = Field(min_length=1, max_length=500)
    method: str = Field(min_length=1, max_length=1000)
    materially_comparable: bool
    unresolved_differences: list[str] = Field(default_factory=list, max_length=30)


OppositionType = Literal[
    "direct_contradiction",
    "boundary_failure",
    "replication_failure",
    "method_critique",
    "alternative_explanation",
    "operational_contradiction",
]


class OppositionCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    subject_claim_id: UUID
    opposing_object_id: UUID
    opposition_type: OppositionType
    comparability: ComparabilityScope
    rationale: str = Field(min_length=10, max_length=10_000)
    recorded_by: str = Field(pattern=_NAME)

    @model_validator(mode="after")
    def direct_conflict_requires_comparability(self) -> OppositionCreate:
        if (
            self.opposition_type in {"direct_contradiction", "replication_failure"}
            and not self.comparability.materially_comparable
        ):
            raise ValueError("direct and replication contradictions must be comparable")
        if self.subject_claim_id == self.opposing_object_id:
            raise ValueError("an object cannot oppose itself")
        return self


class OppositionReviewCreate(StrictModel):
    status: Literal["reviewed", "resolved", "unresolved"]
    resolution: str = Field(min_length=10, max_length=10_000)
    reviewed_by: str = Field(pattern=_NAME)


class OppositionResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    project: str
    subject_claim_id: UUID
    opposing_object_id: UUID
    opposition_type: OppositionType
    comparability: ComparabilityScope
    rationale: str
    status: Literal["proposed", "reviewed", "resolved", "unresolved"]
    resolution: str | None
    supersedes_id: UUID | None
    record_digest: str
    recorded_by: str
    created_at: datetime


class OutcomeScope(StrictModel):
    population: str = Field(min_length=1, max_length=1000)
    horizon: str = Field(min_length=1, max_length=500)
    environment: str = Field(min_length=1, max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=30)


class UncertaintyRecord(StrictModel):
    source: Literal[
        "sampling",
        "measurement",
        "model_form",
        "parameter",
        "environment",
        "implementation",
        "cost",
        "dependency",
        "unresolved_alternative",
    ]
    representation: Literal[
        "distribution", "interval", "scenario", "bound", "sensitivity", "unknown"
    ]
    detail: str = Field(min_length=1, max_length=2000)


class OutcomeCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    evidence_object_id: UUID
    outcome_kind: Literal["valid_negative", "invalid_attempt"]
    question: str = Field(min_length=5, max_length=2000)
    scope: OutcomeScope
    method: str = Field(min_length=3, max_length=10_000)
    uncertainty: list[UncertaintyRecord] = Field(min_length=1, max_length=30)
    failure_mechanisms: list[str] = Field(default_factory=list, max_length=30)
    affected_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    recorded_by: str = Field(pattern=_NAME)

    @model_validator(mode="after")
    def invalid_attempt_has_failure_mechanism(self) -> OutcomeCreate:
        if self.outcome_kind == "invalid_attempt" and not self.failure_mechanisms:
            raise ValueError("invalid attempts require a failure mechanism")
        return self


class OutcomeResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    project: str
    evidence_object_id: UUID
    outcome_kind: Literal["valid_negative", "invalid_attempt"]
    question: str
    scope: OutcomeScope
    method: str
    uncertainty: list[UncertaintyRecord]
    failure_mechanisms: list[str]
    affected_claim_ids: list[UUID]
    record_digest: str
    recorded_by: str
    created_at: datetime


class BeliefAssessment(StrictModel):
    kind: Literal[
        "qualitative", "probabilistic", "interval", "model_relative", "partial_order"
    ]
    value: str = Field(min_length=1, max_length=4000)
    event: str | None = Field(default=None, max_length=1000)
    population: str = Field(min_length=1, max_length=1000)
    horizon: str = Field(min_length=1, max_length=500)
    calibration_basis: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def probability_has_semantics(self) -> BeliefAssessment:
        if self.kind == "probabilistic" and (
            not self.event or not self.calibration_basis
        ):
            raise ValueError("probabilistic beliefs require event and calibration basis")
        return self


class MinorityAssessment(StrictModel):
    reviewer: str = Field(pattern=_NAME)
    assessment: str = Field(min_length=1, max_length=4000)
    evidence_object_ids: list[UUID] = Field(default_factory=list, max_length=100)
    revisit_conditions: list[str] = Field(min_length=1, max_length=30)


class BeliefLedgerCreate(StrictModel):
    object_id: UUID
    content_version: str = Field(min_length=1, max_length=150)
    project: str = Field(pattern=_NAME)
    access_class: Literal["public", "internal", "restricted", "protected"]
    claim_object_id: UUID
    scope: str = Field(min_length=1, max_length=2000)
    assessment: BeliefAssessment
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    opposing_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    synthesis_method: str = Field(min_length=3, max_length=4000)
    uncertainty: list[UncertaintyRecord] = Field(min_length=1, max_length=30)
    dependencies: list[UUID] = Field(default_factory=list, max_length=100)
    owner: str = Field(pattern=_NAME)
    reviewers: list[str] = Field(min_length=1, max_length=20)
    minority_assessments: list[MinorityAssessment] = Field(
        default_factory=list, max_length=20
    )
    valid_from: datetime
    valid_until: datetime | None = None
    review_due: datetime
    invalidation_conditions: list[str] = Field(min_length=1, max_length=30)
    supersedes_object_id: UUID | None = None
    created_by: str = Field(pattern=_NAME)

    @model_validator(mode="after")
    def review_and_validity_are_ordered(self) -> BeliefLedgerCreate:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        if self.review_due <= self.valid_from:
            raise ValueError("review_due must be after valid_from")
        if self.supersedes_object_id == self.object_id:
            raise ValueError("belief cannot supersede itself")
        return self


class EpisodePublishCreate(StrictModel):
    object_id: UUID
    content_version: str = Field(min_length=1, max_length=150)
    project: str = Field(pattern=_NAME)
    access_class: Literal["public", "internal", "restricted", "protected"]
    task_id: UUID | None = None
    question: str = Field(min_length=3, max_length=2000)
    prior_belief_object_id: UUID | None = None
    dossier_id: UUID | None = None
    input_object_ids: list[UUID] = Field(default_factory=list, max_length=200)
    output_object_ids: list[UUID] = Field(default_factory=list, max_length=200)
    decision_object_ids: list[UUID] = Field(default_factory=list, max_length=100)
    tools: list[str] = Field(default_factory=list, max_length=100)
    failures: list[str] = Field(default_factory=list, max_length=100)
    alternatives: list[str] = Field(default_factory=list, max_length=50)
    surprise: str = Field(min_length=1, max_length=4000)
    lessons: list[str] = Field(min_length=1, max_length=100)
    new_questions: list[str] = Field(default_factory=list, max_length=100)
    protected_references: list[str] = Field(default_factory=list, max_length=100)
    created_by: str = Field(pattern=_NAME)


class DossierCompileCreate(StrictModel):
    dossier_key: str = Field(pattern=_KEY)
    version: str = Field(min_length=1, max_length=100)
    project: str = Field(pattern=_NAME)
    access_class: Literal["public", "internal", "restricted", "protected"]
    question: str = Field(min_length=5, max_length=2000)
    decision_context: str = Field(min_length=5, max_length=4000)
    scope: str = Field(min_length=3, max_length=4000)
    evidence_cutoff: datetime
    claim_ids: list[UUID] = Field(min_length=1, max_length=100)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=300)
    opposing_evidence_ids: list[UUID] = Field(default_factory=list, max_length=300)
    belief_ids: list[UUID] = Field(default_factory=list, max_length=100)
    opposition_record_ids: list[UUID] = Field(default_factory=list, max_length=100)
    outcome_record_ids: list[UUID] = Field(default_factory=list, max_length=100)
    episode_ids: list[UUID] = Field(default_factory=list, max_length=100)
    retrieval_manifest: dict[str, Any]
    doctrine_and_authority: list[str] = Field(min_length=1, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=100)
    risks: list[str] = Field(default_factory=list, max_length=100)
    dissent: list[str] = Field(default_factory=list, max_length=100)
    synthesis: str = Field(min_length=10, max_length=20_000)
    recommendation: str = Field(min_length=3, max_length=4000)
    compiler_version: str = Field(min_length=1, max_length=100)
    compiled_by: str = Field(pattern=_NAME)
    expires_at: datetime | None = None


class DossierResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    dossier_key: str
    version: str
    project: str
    access_class: str
    question: str
    decision_context: str
    evidence_cutoff: datetime
    dossier: dict[str, Any]
    record_digest: str
    compiler_version: str
    compiled_by: str
    frozen_at: datetime
    expires_at: datetime | None


class DossierReplayResponse(StrictModel):
    dossier: DossierResponse
    exact_replay: bool
    impacts: list[dict[str, Any]]


class OutcomeSearchResponse(StrictModel):
    query: str
    valid_negative: list[OutcomeResponse]
    invalid_attempt: list[OutcomeResponse]
