import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluatorProfileCreate(BaseModel):
    agent_id: uuid.UUID
    profile_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    review_kinds: list[str] = Field(min_length=1, max_length=20)
    capabilities: list[str] = Field(min_length=1, max_length=50)
    provider: str = Field(min_length=1, max_length=100)
    model_family: str = Field(min_length=1, max_length=120)
    context_group: str = Field(min_length=1, max_length=120)
    registered_by: str = Field(min_length=1, max_length=150)


class ProducerIdentity(BaseModel):
    actor: str = Field(min_length=1, max_length=150)
    agent_id: uuid.UUID | None = None
    machine: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    model_family: str = Field(min_length=1, max_length=120)
    runtime: str = Field(min_length=1, max_length=120)
    context_group: str = Field(min_length=1, max_length=120)
    package_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvaluationRouteCreate(BaseModel):
    subject_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,59}$")
    subject_id: str = Field(min_length=1, max_length=150)
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: ProducerIdentity
    excluded_producers: list[ProducerIdentity] = Field(default_factory=list, max_length=10)
    required_review_kinds: list[str] = Field(min_length=1, max_length=10)
    required_capabilities: list[str] = Field(default_factory=list, max_length=20)
    max_pairwise_shared_dimensions: int = Field(default=4, ge=0, le=4)
    requested_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def unique_review_kinds(self):
        if len(set(self.required_review_kinds)) != len(self.required_review_kinds):
            raise ValueError("required_review_kinds must be unique")
        return self


class AlphaStrategyReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["approve", "reject"]
    rationale: str = Field(min_length=20, max_length=4000)
    checks: list[str] = Field(min_length=1, max_length=30)
    blockers: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def consistent_verdict(self):
        if self.verdict == "approve" and self.blockers:
            raise ValueError("Approved reviews cannot contain unresolved blockers")
        return self


class EvaluatorAssignmentComplete(BaseModel):
    evaluator_agent_id: uuid.UUID
    review_id: str = Field(min_length=1, max_length=150)
    review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    alpha_strategy_review: AlphaStrategyReview | None = None


class EvaluatorProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    profile_version: str
    status: str
    review_kinds: list[str]
    capabilities: list[str]
    machine: str
    provider: str
    model_family: str
    runtime: str
    context_group: str
    package_id: uuid.UUID
    package_digest: str
    profile_digest: str
    registered_by: str
    created_at: datetime


class EvaluationRouteResponse(BaseModel):
    id: uuid.UUID
    subject_type: str
    subject_id: str
    subject_digest: str
    producer: dict
    policy: dict
    status: str
    route_digest: str
    requested_by: str
    blocked_reason: dict
    created_at: datetime
    completed_at: datetime | None
    assignments: list[dict]
    events: list[dict]
    independence_receipt: dict | None


class IndependenceAssertionResponse(BaseModel):
    route_id: uuid.UUID
    verdict: Literal["independence_demonstrated"]
    receipt_digest: str
    assertion: dict
