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
    manifest: ExperimentManifest
    manifest_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


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
