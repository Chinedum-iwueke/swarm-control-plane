from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ConsequenceAction = Literal["promote", "demote", "quarantine", "retire", "reinstate"]
LifecycleDimension = Literal["research", "evidence", "operations", "capital"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsequenceCreate(StrictModel):
    command_id: UUID
    actor: str = Field(min_length=2, max_length=150)
    action: ConsequenceAction
    dimension: LifecycleDimension
    expected_version: int = Field(ge=0)
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: list[str] = Field(min_length=1, max_length=100)
    evidence_epoch: datetime
    approvers: list[str] = Field(min_length=1, max_length=20)
    affected_descendants: list[str] = Field(default_factory=list, max_length=500)
    expires_at: datetime
    reason: str = Field(min_length=20, max_length=2000)
    risk_level: int = Field(ge=0, le=3)
    environment: str = Field(default="internal", max_length=80)
    originator: str | None = None
    evaluator: str | None = None
    active_veto_roles: list[str] = Field(default_factory=list)

    @field_validator("evidence")
    @classmethod
    def digest_evidence(cls, value: list[str]) -> list[str]:
        if any(
            len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
            for item in value
        ):
            raise ValueError("evidence references must be SHA-256 digests")
        return value

    @model_validator(mode="after")
    def bounded_and_independent(self):
        now = datetime.now(UTC)
        for value, name in (
            (self.evidence_epoch, "evidence_epoch"),
            (self.expires_at, "expires_at"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        if self.evidence_epoch > now + timedelta(
            seconds=30
        ) or self.evidence_epoch < now - timedelta(days=7):
            raise ValueError("evidence epoch is stale or in the future")
        if self.expires_at <= now or self.expires_at > now + timedelta(days=30):
            raise ValueError("consequence expiry is outside the bounded interval")
        if (
            len(set(self.approvers)) != len(self.approvers)
            or self.actor not in self.approvers
        ):
            raise ValueError(
                "approvers must be unique and include the accountable actor"
            )
        if self.action in {"promote", "reinstate"} and (
            len(self.approvers) < 2
            or not self.originator
            or not self.evaluator
            or self.originator in self.approvers
            or self.evaluator not in self.approvers
        ):
            raise ValueError("promotion and reinstatement require independent approval")
        return self


class ConsequenceReverse(StrictModel):
    command_id: UUID
    actor: str = Field(min_length=2, max_length=150)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=20, max_length=2000)
    risk_level: int = Field(ge=0, le=3)
    environment: str = "internal"
    originator: str = Field(min_length=2, max_length=150)
    evaluator: str = Field(min_length=2, max_length=150)
    active_veto_roles: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def independent_participants(self):
        if self.actor in {self.originator, self.evaluator}:
            raise ValueError("consequence reversal requires independent participants")
        return self


class ConsequenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID
    command_id: UUID
    action: ConsequenceAction
    status: str
    prior_state: str
    resulting_state: str
    rollback_state: str
    approvers: list[str]
    affected_descendants: list[str]
    evidence_epoch: datetime
    expires_at: datetime
    reversed_by_id: UUID | None
    reversal_of_id: UUID | None
    reason: str
    record_digest: str
    created_at: datetime


class ConsequenceListResponse(StrictModel):
    items: list[ConsequenceResponse]
    count: int
