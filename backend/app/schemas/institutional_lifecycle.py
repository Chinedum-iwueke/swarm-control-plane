from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

LifecycleDimension = Literal["research", "evidence", "operations", "capital"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LifecycleSubjectCreate(StrictModel):
    subject_type: str = Field(pattern=r"^[a-z][a-z0-9-]{1,79}$")
    subject_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class InstitutionalTransitionCreate(StrictModel):
    command_id: UUID
    actor: str = Field(min_length=2, max_length=150)
    dimension: LifecycleDimension
    command: str = Field(pattern=r"^[a-z][a-z0-9-]{1,79}$")
    expected_version: int = Field(ge=0)
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=10, max_length=2000)
    risk_level: int = Field(ge=0, le=3)
    environment: str = Field(default="internal", max_length=80)
    requester: str | None = None
    originator: str | None = None
    evaluator: str | None = None
    active_veto_roles: list[str] = Field(default_factory=list)
    authority_exception_id: UUID | None = None
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must include a timezone")
        return value


class LifecycleProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    subject_type: str
    subject_id: str
    subject_digest: str
    dimension: LifecycleDimension
    state: str
    version: int
    last_event_digest: str | None
    updated_at: datetime


class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    projection_id: UUID
    command_id: UUID
    dimension: LifecycleDimension
    command: str
    prior_state: str
    resulting_state: str
    actor: str
    authority_decision_id: UUID
    expected_version: int
    resulting_version: int
    reason: str
    evidence: list[str]
    prior_event_digest: str | None
    record_digest: str
    effective_at: datetime
    created_at: datetime


class LifecycleDossierResponse(StrictModel):
    subject_type: str
    subject_id: str
    subject_digest: str
    projections: list[LifecycleProjectionResponse]
    events: list[LifecycleEventResponse]
    dossier_digest: str


class LifecycleProjectionListResponse(StrictModel):
    items: list[LifecycleProjectionResponse]
    count: int
