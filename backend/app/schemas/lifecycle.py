from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

LifecycleState = Literal["active", "consolidated", "superseded", "retracted", "expired", "deleted"]
LifecycleAction = Literal[
    "consolidate", "supersede", "correct", "retract", "expire", "decay", "restore"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LifecycleActionCreate(StrictModel):
    action: LifecycleAction
    authority: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    reason: str = Field(min_length=1, max_length=4000)
    successor_object_id: UUID | None = None
    effective_at: datetime

    @model_validator(mode="after")
    def successor_matches_action(self) -> LifecycleActionCreate:
        needs_successor = self.action in {"consolidate", "supersede", "correct"}
        if needs_successor != (self.successor_object_id is not None):
            raise ValueError("successor_object_id is required only for successor actions")
        return self


class RetentionHoldCreate(StrictModel):
    authority: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    reason: str = Field(min_length=1, max_length=4000)
    active: bool


class DeletionRequestCreate(StrictModel):
    requested_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    legal_basis: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=4000)


class DeletionDecisionCreate(StrictModel):
    decision: Literal["approve", "reject"]
    decided_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    reason: str = Field(min_length=1, max_length=4000)


class LifecycleStateResponse(StrictModel):
    object_id: UUID
    state: LifecycleState
    active_for_retrieval: bool
    successor_object_id: UUID | None
    retention_hold: bool
    hold_authority: str | None
    hold_reason: str | None
    effective_at: datetime
    version: int
    updated_at: datetime


class LifecycleEventResponse(StrictModel):
    id: UUID
    object_id: UUID
    event_type: str
    prior_state: LifecycleState
    resulting_state: LifecycleState
    successor_object_id: UUID | None
    authority: str
    legal_basis: str | None
    reason: str
    detail: dict
    record_digest: str
    effective_at: datetime
    created_at: datetime


class LifecycleImpactResponse(StrictModel):
    id: UUID
    event_id: UUID
    object_id: UUID
    impact: dict
    record_digest: str
    created_at: datetime


class LifecycleDossierResponse(StrictModel):
    state: LifecycleStateResponse
    events: list[LifecycleEventResponse]
    impacts: list[LifecycleImpactResponse]
    dossier_digest: str


class LifecycleStateListResponse(StrictModel):
    items: list[LifecycleStateResponse]
    count: int


class DeletionRequestResponse(StrictModel):
    id: UUID
    object_id: UUID
    status: Literal["pending", "approved", "rejected"]
    requested_by: str
    legal_basis: str
    reason: str
    payload_digest: str
    decided_by: str | None
    decision_reason: str | None
    record_digest: str
    created_at: datetime
    decided_at: datetime | None
