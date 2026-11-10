import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskEventResponse, TaskResponse

ProviderCircuitState = Literal["closed", "open", "half_open"]


class ProviderCapacityDeferral(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=1)
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=50)
    failure_summary: str = Field(min_length=1, max_length=2000)
    retry_after_seconds: int = Field(default=900, ge=60, le=21_600)


class ProviderProbeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["healthy", "exhausted"]
    failure_summary: str | None = Field(default=None, max_length=2000)
    retry_after_seconds: int = Field(default=900, ge=60, le=21_600)


class ProviderCapacityCircuitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    state: ProviderCircuitState
    generation: int
    consecutive_failures: int
    blocked_capabilities: list[str]
    failure_summary: str | None
    source_task_id: uuid.UUID | None
    probe_agent_id: uuid.UUID | None
    opened_at: datetime | None
    next_probe_at: datetime | None
    probe_expires_at: datetime | None
    recovered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderProbeResponse(BaseModel):
    circuit: ProviderCapacityCircuitResponse
    notification_created: bool = False


class ProviderCapacityDeferralResponse(BaseModel):
    task: TaskResponse
    event: TaskEventResponse
    circuit: ProviderCapacityCircuitResponse
    notification_created: bool = False
