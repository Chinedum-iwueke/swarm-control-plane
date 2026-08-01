from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_ACTOR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperationalNoteCreate(StrictModel):
    note_key: str = Field(pattern=_KEY, max_length=150)
    subject: str = Field(min_length=3, max_length=300)
    finding: str = Field(min_length=10, max_length=8000)
    evidence: list[str] = Field(min_length=1, max_length=50)
    affected_systems: list[str] = Field(min_length=1, max_length=30)
    urgency: Literal["low", "medium", "high", "critical"]
    proposed_owner: str = Field(pattern=_ACTOR, max_length=150)
    deferral_reason: str | None = Field(default=None, max_length=2000)
    milestone_refs: list[str] = Field(default_factory=list, max_length=30)
    repository_refs: list[str] = Field(default_factory=list, max_length=30)
    created_by: str = Field(pattern=_ACTOR, max_length=150)


class AgentOperationalNoteCreate(StrictModel):
    note_key: str = Field(pattern=_KEY, max_length=150)
    subject: str = Field(min_length=3, max_length=300)
    finding: str = Field(min_length=10, max_length=8000)
    evidence: list[str] = Field(min_length=1, max_length=50)
    affected_systems: list[str] = Field(min_length=1, max_length=30)
    urgency: Literal["low", "medium", "high", "critical"]
    proposed_owner: str = Field(pattern=_ACTOR, max_length=150)
    deferral_reason: str | None = Field(default=None, max_length=2000)
    milestone_refs: list[str] = Field(default_factory=list, max_length=30)
    repository_refs: list[str] = Field(default_factory=list, max_length=30)


class OperationalNoteTransition(StrictModel):
    action: Literal["assign", "defer", "resolve", "reopen"]
    actor: str = Field(pattern=_ACTOR, max_length=150)
    reason: str = Field(min_length=10, max_length=2000)
    assigned_to: str | None = Field(default=None, pattern=_ACTOR, max_length=150)
    deferred_until: datetime | None = None
    evidence: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def action_requirements(self) -> OperationalNoteTransition:
        if self.action == "assign" and self.assigned_to is None:
            raise ValueError("assign requires assigned_to")
        if self.action == "defer" and self.deferred_until is None:
            raise ValueError("defer requires deferred_until")
        if self.action == "resolve" and not self.evidence:
            raise ValueError("resolve requires resolution evidence")
        return self


class OperationalNoteProposalRequest(StrictModel):
    requested_by: str = Field(pattern=_ACTOR, max_length=150)
    objective: str = Field(min_length=10, max_length=2000)


class OperationalNoteEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    note_id: uuid.UUID
    event_type: str
    previous_status: str | None
    new_status: str
    actor: str
    reason: str
    evidence: list[str]
    created_at: datetime


class OperationalNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    note_key: str
    subject: str
    finding: str
    evidence: list[str]
    affected_systems: list[str]
    urgency: str
    proposed_owner: str
    deferral_reason: str | None
    milestone_refs: list[str]
    repository_refs: list[str]
    status: str
    assigned_to: str | None
    deferred_until: datetime | None
    resolution_evidence: list[str]
    record_digest: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class OperationalNoteDetail(OperationalNoteResponse):
    events: list[OperationalNoteEventResponse]
