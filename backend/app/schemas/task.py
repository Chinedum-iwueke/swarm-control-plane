from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal[
    "queued",
    "leased",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "pending_approval",
]


class TaskCreate(BaseModel):
    task_number: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )

    project: str = Field(min_length=1, max_length=100)
    task_type: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1)

    priority: int = Field(default=50, ge=0, le=100)
    risk_level: int = Field(default=0, ge=0, le=5)

    parent_task_id: uuid.UUID | None = None
    created_by: str = Field(min_length=1, max_length=150)

    input_contract: dict = Field(default_factory=dict)
    expected_outputs: list = Field(default_factory=list)
    acceptance_criteria: list = Field(default_factory=list)
    approval_policy: dict = Field(default_factory=dict)
    approval_required: bool = False

    required_capabilities: list[str] = Field(default_factory=list)
    allowed_machines: list[str] = Field(default_factory=list)

    max_attempts: int = Field(default=3, ge=1, le=20)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_number: str
    project: str
    task_type: str
    title: str
    objective: str
    status: str
    priority: int
    risk_level: int

    assigned_agent_id: uuid.UUID | None
    parent_task_id: uuid.UUID | None
    mission_id: uuid.UUID | None
    milestone_step_id: str | None
    created_by: str

    input_contract: dict
    expected_outputs: list
    acceptance_criteria: list
    approval_policy: dict
    approval_required: bool
    plan_digest: str

    required_capabilities: list[str]
    allowed_machines: list[str]

    max_attempts: int
    attempt_count: int

    leased_at: datetime | None
    lease_expires_at: datetime | None
    last_execution_heartbeat_at: datetime | None

    result: dict
    failure: dict

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: uuid.UUID
    agent_id: uuid.UUID | None
    event_type: str
    attempt_number: int
    message: str
    payload: dict
    created_at: datetime


class TaskDetailResponse(BaseModel):
    task: TaskResponse
    events: list[TaskEventResponse]


class TaskLeaseRequest(BaseModel):
    lease_seconds: int = Field(default=300, ge=60, le=1800)


class TaskLeaseResponse(BaseModel):
    task: TaskResponse | None
    lease_token: str | None
    paused: bool = False
    pause_reasons: list[str] = Field(default_factory=list)


class TaskLeaseMutation(BaseModel):
    lease_token: str = Field(min_length=1)


class TaskStartRequest(TaskLeaseMutation):
    message: str = Field(
        default="Task execution started.",
        min_length=1,
        max_length=2000,
    )


class TaskExecutionHeartbeatRequest(TaskLeaseMutation):
    lease_seconds: int = Field(default=300, ge=60, le=1800)

    message: str = Field(
        default="Task execution heartbeat received.",
        min_length=1,
        max_length=2000,
    )

    progress: dict = Field(default_factory=dict)


class TaskCompleteRequest(TaskLeaseMutation):
    message: str = Field(
        default="Task completed successfully.",
        min_length=1,
        max_length=2000,
    )

    result: dict = Field(default_factory=dict)


class TaskFailRequest(TaskLeaseMutation):
    message: str = Field(
        default="Task execution failed.",
        min_length=1,
        max_length=2000,
    )

    failure: dict = Field(default_factory=dict)
    retryable: bool = False


class TaskResumeRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


class TaskReleaseRequest(TaskLeaseMutation):
    message: str = Field(
        default="Task lease released by worker.",
        min_length=1,
        max_length=2000,
    )


class TaskMutationResponse(BaseModel):
    task: TaskResponse
    event: TaskEventResponse


class ExpiredLeaseReapResponse(BaseModel):
    inspected: int
    requeued: int
    failed: int
