from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentRuntimeStatus = Literal["idle", "busy", "degraded"]


class AgentHeartbeat(BaseModel):
    status: AgentRuntimeStatus = "idle"
    runtime: str = Field(default="hermes", min_length=1, max_length=100)
    runtime_version: str | None = Field(default=None, max_length=100)
    capabilities: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentIdentity(BaseModel):
    id: UUID
    slug: str
    display_name: str
    role: str
    machine: str
    hermes_profile: str
    runtime: str | None
    runtime_version: str | None
    status: str
    presence: str
    capabilities: list[str]
    heartbeat_metadata: dict[str, Any]
    risk_ceiling: int
    is_enabled: bool
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentHeartbeatResponse(BaseModel):
    agent_id: UUID
    status: str
    presence: str
    received_at: datetime


class Task(BaseModel):
    id: UUID
    task_number: str
    project: str
    task_type: str
    title: str
    objective: str
    status: str
    priority: int
    risk_level: int
    assigned_agent_id: UUID | None
    parent_task_id: UUID | None
    created_by: str
    input_contract: dict[str, Any]
    expected_outputs: list[Any]
    acceptance_criteria: list[Any]
    approval_policy: dict[str, Any]
    required_capabilities: list[str]
    allowed_machines: list[str]
    max_attempts: int
    attempt_count: int
    leased_at: datetime | None
    lease_expires_at: datetime | None
    last_execution_heartbeat_at: datetime | None
    result: dict[str, Any]
    failure: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskLeaseRequest(BaseModel):
    lease_seconds: int = Field(default=300, ge=60, le=1800)


class LeaseResponse(BaseModel):
    task: Task | None
    lease_token: str | None


class TaskStartRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    message: str = Field(
        default="Task execution started.",
        min_length=1,
        max_length=2000,
    )


class TaskExecutionHeartbeatRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    lease_seconds: int = Field(default=300, ge=60, le=1800)
    message: str = Field(
        default="Task execution heartbeat received.",
        min_length=1,
        max_length=2000,
    )
    progress: dict[str, Any] = Field(default_factory=dict)


class TaskCompleteRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    message: str = Field(
        default="Task completed successfully.",
        min_length=1,
        max_length=2000,
    )
    result: dict[str, Any] = Field(default_factory=dict)


class TaskFailRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    message: str = Field(
        default="Task execution failed.",
        min_length=1,
        max_length=2000,
    )
    failure: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False


class TaskReleaseRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    message: str = Field(
        default="Task lease released by worker.",
        min_length=1,
        max_length=2000,
    )


class TaskEvent(BaseModel):
    id: int
    task_id: UUID
    agent_id: UUID | None
    event_type: str
    attempt_number: int
    message: str
    payload: dict[str, Any]
    created_at: datetime


class TaskMutationResponse(BaseModel):
    task: Task
    event: TaskEvent


class ExecutionResult(BaseModel):
    success: bool
    workflow: str
    repository: str
    workspace: str
    return_codes: dict[str, int] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error: str | None = None


class StepExecutionResult(BaseModel):
    name: str
    success: bool
    return_code: int | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    timed_out: bool = False
    stdout_log: str
    stderr_log: str


class WorkflowExecutionResult(BaseModel):
    workflow: str
    repository: str
    base_commit: str
    task_attempt: int
    total_duration_seconds: float
    steps: list[StepExecutionResult]
    success: bool
    heartbeat_failures: list[str] = Field(default_factory=list)
    termination_reason: str | None = None
