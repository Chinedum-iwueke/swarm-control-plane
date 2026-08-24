from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OperationState = Literal[
    "queued",
    "waiting_approval",
    "running",
    "blocked",
    "stalled",
    "succeeded",
    "failed",
    "cancelled",
]


class OperationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str = Field(min_length=3, max_length=240)
    kind: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=2, max_length=300)
    project: str = Field(min_length=2, max_length=100)
    machine: str | None = Field(default=None, max_length=100)
    owner_type: Literal["task", "mission", "service", "timer", "system", "agent"]
    owner_id: str | None = Field(default=None, max_length=150)
    state: OperationState
    phase: str = Field(min_length=1, max_length=120)
    progress_mode: Literal["determinate", "indeterminate"] = "indeterminate"
    progress_current: int | None = Field(default=None, ge=0)
    progress_total: int | None = Field(default=None, ge=1)
    progress_unit: str | None = Field(default=None, max_length=40)
    cancellable: bool = False
    retryable: bool = False
    error_summary: str | None = Field(default=None, max_length=4000)
    links: dict = Field(default_factory=dict)
    detail: dict = Field(default_factory=dict)
    input_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def progress_is_coherent(self):
        if self.progress_mode == "determinate":
            if self.progress_current is None or self.progress_total is None:
                raise ValueError("determinate progress requires current and total")
            if self.progress_current > self.progress_total:
                raise ValueError("progress_current cannot exceed progress_total")
        elif self.progress_current is not None or self.progress_total is not None:
            raise ValueError("indeterminate progress cannot declare current or total")
        return self


class OperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_key: str
    kind: str
    title: str
    project: str
    machine: str | None
    owner_type: str
    owner_id: str | None
    state: str
    phase: str
    progress_mode: str
    progress_current: int | None
    progress_total: int | None
    progress_unit: str | None
    heartbeat_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancellable: bool
    retryable: bool
    error_summary: str | None
    links: dict
    detail: dict
    input_digest: str | None
    record_digest: str
    created_at: datetime
    updated_at: datetime


class OperationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operation_id: UUID
    sequence: int
    event_type: str
    state: str
    phase: str
    actor: str
    detail: dict
    record_digest: str
    created_at: datetime
