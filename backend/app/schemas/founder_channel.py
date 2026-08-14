import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance import ApprovalResponse


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FounderChannelRequest(StrictModel):
    kind: Literal["task", "mission"]
    project: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    title: str = Field(min_length=3, max_length=160)
    objective: str = Field(min_length=10, max_length=4000)
    risk_level: int = Field(default=0, ge=0, le=5)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)


class FounderChannelDecision(StrictModel):
    reason: str = Field(min_length=10, max_length=1000)
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)


class FounderChannelApproval(ApprovalResponse):
    task_number: str
    task_title: str
    operation: str | None
    milestone_step_id: str | None
    mission_id: uuid.UUID | None
    task_status: str
    actionable: bool
    blocked_by: list[str]
    mission_deadline_at: datetime | None


class FounderChannelMission(BaseModel):
    id: uuid.UUID
    milestone_id: str
    objective: str
    status: str
    manifest_digest: str
    supervision_status: str
    supervision_policy: dict
    supervision_exception: dict
    deadline_at: datetime
    actionable: bool


class FounderNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    entity_id: uuid.UUID
    deduplication_key: str
    state: str
    payload: dict
    created_at: datetime


class FounderNotificationAcknowledgement(StrictModel):
    delivery_reference: str = Field(min_length=1, max_length=200)
