import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AgentRuntimeStatus = Literal["idle", "busy", "degraded"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    conversation_id: UUID | None = None
    conversation_revision: int | None = None
    mission_id: UUID | None = None
    milestone_step_id: str | None = None
    created_by: str
    input_contract: dict[str, Any]
    expected_outputs: list[Any]
    acceptance_criteria: list[Any]
    approval_policy: dict[str, Any]
    approval_required: bool = False
    plan_digest: str = ""
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
    paused: bool = False
    pause_reasons: list[str] = Field(default_factory=list)


class AgentContextManifest(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: UUID
    attempt_number: int
    schema_version: str
    purpose: str
    authorization_snapshot_digest: str
    items: list[dict[str, Any]]
    context_pack_digest: str
    manifest_digest: str
    item_count: int
    byte_count: int
    status: str
    expires_at: datetime
    created_by: str
    created_at: datetime


class ContextReplayRequest(BaseModel):
    lease_token: str


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


class ProposalCodeValidationContract(StrictModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    workflow: Literal["code-validation"]
    base_ref: str = Field(min_length=1, max_length=255)


class ProposalEngineeringMissionContract(StrictModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    workflow: Literal["engineering-mission"]
    base_ref: str = Field(min_length=1, max_length=255)
    milestone_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    work_item_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    objective: str = Field(min_length=10, max_length=4000)
    allowed_paths: list[str] = Field(min_length=1, max_length=50)
    context_paths: list[str] = Field(default_factory=list, max_length=50)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=50)
    stop_conditions: list[str] = Field(min_length=1, max_length=20)
    max_files_changed: int = Field(ge=1, le=100)
    max_diff_lines: int = Field(ge=1, le=10000)
    max_duration_seconds: int = Field(ge=60, le=86400)


class ProposalInfrastructureParameters(StrictModel):
    service: Literal["api", "postgres", "pgbouncer", "redis"] | None = None
    certificate_profile: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )


class ProposalInfrastructureContract(StrictModel):
    runbook: Literal[
        "vm2-infrastructure",
        "vm2-postgres-deployment",
        "vm2-platform-operations",
    ]
    runbook_version: Literal["1.0.0"]
    operation: Literal[
        "observe-control-plane",
        "restart-control-plane-api",
        "preflight-invariance-postgres",
        "stage-invariance-postgres",
        "start-invariance-postgres-private",
        "initialize-invariance-schema",
        "configure-invariance-backups",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
        "verify-docker-service",
        "restart-docker-service",
        "verify-redis",
        "verify-storage",
        "verify-certificate",
        "verify-backup",
        "verify-service-health",
    ]
    target: Literal[
        "vm2-control-plane",
        "vm2-invariance-postgres",
        "vm2-production",
    ]
    parameters: ProposalInfrastructureParameters
    package_name: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    package_version: str | None = Field(
        default=None, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"
    )
    package_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ProposalResearchAcceptance(StrictModel):
    minimum_out_of_sample_sharpe: float = Field(ge=-10, le=10)
    maximum_out_of_sample_drawdown: float = Field(ge=0, le=1)
    minimum_out_of_sample_trades: int = Field(ge=1, le=10000)
    minimum_cost_stress_sharpe: float = Field(ge=-10, le=10)


class ProposalResearchExperimentContract(StrictModel):
    repository: Literal["bulletproof_bt"]
    workflow: Literal["research-experiment"]
    base_ref: str = Field(min_length=1, max_length=255)
    program_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    hypothesis_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    hypothesis: Literal["lagged-return-momentum", "btc-hourly-lagged-return"]
    dataset: Literal["synthetic-regime-v1", "binance-btcusdt-1h-2025"]
    dataset_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    experiment_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trial_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, le=2_147_483_647)
    observations: int = Field(ge=500, le=10000)
    train_fraction: float = Field(ge=0.5, le=0.8)
    transaction_cost_bps: float = Field(ge=0, le=100)
    acceptance: ProposalResearchAcceptance


class ProposalResearchMemorySyncContract(StrictModel):
    repository: Literal["bulletproof_bt"]
    workflow: Literal["research-memory-sync"]
    base_ref: str = Field(min_length=1, max_length=255)


ProposalInputContract = (
    ProposalCodeValidationContract
    | ProposalEngineeringMissionContract
    | ProposalInfrastructureContract
    | ProposalResearchExperimentContract
    | ProposalResearchMemorySyncContract
)


class ProposalApprovalPolicy(StrictModel):
    kind: Literal["automatic", "explicit", "registry_gate"]
    risk: int = Field(ge=0, le=5)


class ProposedTask(StrictModel):
    project: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    task_type: Literal[
        "code_validation",
        "engineering_mission",
        "infrastructure_observation",
        "infrastructure_operation",
        "research_experiment",
        "research_memory_sync",
    ]
    title: str = Field(min_length=3, max_length=300)
    objective: str = Field(min_length=10, max_length=8000)
    priority: int = Field(default=50, ge=0, le=100)
    risk_level: int = Field(default=0, ge=0, le=5)
    input_contract: ProposalInputContract
    expected_outputs: list[str] = Field(default_factory=list, max_length=30)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=30)
    approval_policy: ProposalApprovalPolicy
    approval_required: bool = False
    required_capabilities: list[str] = Field(default_factory=list, max_length=30)
    allowed_machines: list[str] = Field(default_factory=list, max_length=20)
    max_attempts: int = Field(default=1, ge=1, le=5)

    @model_validator(mode="after")
    def no_execution_surface(self) -> "ProposedTask":
        forbidden = {"command", "commands", "shell", "script", "argv", "executable"}

        def inspect(value: object) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if str(key).lower() in forbidden:
                        raise ValueError(
                            "proposal contains an execution command surface"
                        )
                    inspect(nested)
            elif isinstance(value, list):
                for nested in value:
                    inspect(nested)

        inspect(self.input_contract)
        expected = {
            "code_validation": ProposalCodeValidationContract,
            "engineering_mission": ProposalEngineeringMissionContract,
            "infrastructure_observation": ProposalInfrastructureContract,
            "infrastructure_operation": ProposalInfrastructureContract,
            "research_experiment": ProposalResearchExperimentContract,
            "research_memory_sync": ProposalResearchMemorySyncContract,
        }
        if not isinstance(self.input_contract, expected[self.task_type]):
            raise TypeError("proposal task type does not match its input contract")
        if self.task_type in {"code_validation", "engineering_mission"}:
            machines = ["vm1-developer"]
            capabilities = ["git", "python", "testing"]
        elif self.task_type == "research_experiment":
            machines = ["vm1-developer"]
            capabilities = ["git", "python", "backtesting", "research-audit"]
        elif self.task_type == "research_memory_sync":
            machines = ["vm1-developer"]
            capabilities = ["git", "python", "research-memory-sync"]
        elif self.input_contract.runbook == "vm2-infrastructure":
            machines = ["vm2-deployment"]
            capabilities = [
                "infrastructure-observation",
                "service-health",
                "controlled-restart",
            ]
        else:
            machines = ["vm2-deployment"]
            capabilities = [
                "deployment-architecture",
                "infrastructure-observation",
                "postgres-deployment",
                "service-health",
            ]
        if self.allowed_machines != machines:
            raise ValueError("proposal does not use the canonical machine route")
        if self.required_capabilities != capabilities:
            raise ValueError("proposal does not use the canonical capability route")
        if self.approval_policy.risk != self.risk_level:
            raise ValueError("proposal approval risk does not match task risk")
        return self


class ProposalDefaultDecision(StrictModel):
    field: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1000)
    basis: str = Field(min_length=3, max_length=1000)
    policy_version: str = Field(min_length=1, max_length=100)
    confidence: Literal["high", "medium", "low"]
    alternatives: list[str] = Field(default_factory=list, max_length=10)


class FounderProposalDocument(StrictModel):
    schema_version: Literal[1]
    summary: str = Field(min_length=10, max_length=1000)
    interpretation: str = Field(min_length=10, max_length=4000)
    recommended_action: Literal["create_task", "needs_clarification", "decline"]
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    clarification_questions: list[str] = Field(default_factory=list, max_length=20)
    target_role: str | None = Field(default=None, max_length=150)
    target_role_reason: str | None = Field(default=None, max_length=1000)
    safety_constraints: list[str] = Field(default_factory=list, max_length=20)
    unresolved_fields: list[str] = Field(default_factory=list, max_length=30)
    specification_format: dict[str, str] = Field(default_factory=dict)
    resolved_defaults: list[ProposalDefaultDecision] = Field(
        default_factory=list, max_length=30
    )
    proposed_task: ProposedTask | None = None

    @model_validator(mode="after")
    def task_matches_action(self) -> "FounderProposalDocument":
        if self.recommended_action == "create_task" and self.proposed_task is None:
            raise ValueError("create_task requires proposed_task")
        if self.recommended_action != "create_task" and self.proposed_task is not None:
            raise ValueError("only create_task may include proposed_task")
        if self.recommended_action == "needs_clarification":
            if not self.clarification_questions or not self.unresolved_fields:
                raise ValueError(
                    "needs_clarification requires questions and unresolved fields"
                )
            missing_formats = set(self.unresolved_fields) - set(
                self.specification_format
            )
            if missing_formats:
                raise ValueError(
                    "each unresolved field requires accepted format guidance"
                )
        elif self.unresolved_fields:
            raise ValueError("only needs_clarification may contain unresolved fields")
        return self


class FounderProposalCreate(StrictModel):
    lease_token: str = Field(min_length=1)
    proposal: FounderProposalDocument


class FounderProposalResponse(StrictModel):
    id: UUID
    source_task_id: UUID
    conversation_id: UUID | None = None
    conversation_revision: int | None = None
    planner_agent_id: UUID
    status: str
    proposal: FounderProposalDocument
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_reason: str | None
    decided_by: str | None
    materialized_task_id: UUID | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None


class ArtifactCreateRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    artifact_type: Literal["log", "report", "result", "evidence"]
    name: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    location: str = Field(min_length=1, max_length=2000)
    storage_backend: Literal["workspace", "object"]
    workflow: str
    workflow_version: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    confidentiality: Literal["internal", "confidential", "restricted"] = "internal"
    retention_class: Literal["ephemeral", "standard", "audit", "legal"] = "audit"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: UUID
    attempt_number: int
    artifact_type: str
    name: str
    size_bytes: int
    sha256: str
    location: str
    storage_backend: str
    workflow: str
    workflow_version: str
    source_commit: str
    confidentiality: str
    retention_class: str
    verification_status: str
    expires_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime


class ResearchMemoryRegistrationRequest(StrictModel):
    export: dict[str, Any]
    export_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: str = Field(min_length=1, max_length=19000)
    summary_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchMemoryRegistrationResponse(StrictModel):
    export: dict[str, Any]
    document_key: str
    unchanged: bool
    canonical_ingestion_job_id: UUID
    canonical_object_ids: list[UUID]
    corpus_sync_run_id: UUID


class InfrastructureContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runbook: Literal[
        "vm2-infrastructure",
        "vm2-postgres-deployment",
        "vm2-platform-operations",
    ]
    runbook_version: Literal["1.0.0"]
    operation: Literal[
        "observe-control-plane",
        "restart-control-plane-api",
        "preflight-invariance-postgres",
        "stage-invariance-postgres",
        "start-invariance-postgres-private",
        "initialize-invariance-schema",
        "configure-invariance-backups",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
        "verify-docker-service",
        "restart-docker-service",
        "verify-redis",
        "verify-storage",
        "verify-certificate",
        "verify-backup",
        "verify-service-health",
    ]
    target: Literal[
        "vm2-control-plane",
        "vm2-invariance-postgres",
        "vm2-production",
    ]
    parameters: dict[str, Any] = Field(default_factory=dict)
    package_name: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    package_version: str | None = Field(
        default=None, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"
    )
    package_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def no_untyped_parameters(self) -> "InfrastructureContract":
        if self.runbook != "vm2-platform-operations" and self.parameters:
            raise ValueError("This operation does not accept parameters.")
        package_values = (
            self.package_name,
            self.package_version,
            self.package_digest,
        )
        if self.runbook == "vm2-platform-operations":
            if not all(package_values) or self.package_name != self.runbook:
                raise ValueError("Packaged operations require matching attestation.")
        elif any(package_values):
            raise ValueError("Legacy operations cannot claim package attestation.")
        return self


class BrokerTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str = Field(min_length=1)


class BrokerTicketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    task_id: UUID
    task_number: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    attempt_number: int = Field(ge=1)
    agent_id: UUID
    machine: Literal["vm2-deployment"]
    task_type: Literal["infrastructure_observation", "infrastructure_operation"]
    risk_level: int = Field(ge=0, le=5)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract: InfrastructureContract
    nonce: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def operation_matches_task_type(self) -> "BrokerTicketPayload":
        observations = {
            "observe-control-plane",
            "preflight-invariance-postgres",
            "verify-invariance-postgres",
            "prepare-invariance-cutover",
            "verify-docker-service",
            "verify-redis",
            "verify-storage",
            "verify-certificate",
            "verify-backup",
            "verify-service-health",
        }
        expected = (
            "infrastructure_observation"
            if self.contract.operation in observations
            else "infrastructure_operation"
        )
        if self.task_type != expected:
            raise ValueError("operation does not match task type")
        if self.expires_at <= self.issued_at:
            raise ValueError("ticket expiry must follow issuance")
        return self


class BrokerTicketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: BrokerTicketPayload
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")


class BrokerExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool
    operation: str
    task_id: UUID
    attempt_number: int
    started_at: datetime
    ended_at: datetime
    pre_state: dict[str, Any]
    action: dict[str, Any] | None = None
    post_state: dict[str, Any] | None = None
    rollback: dict[str, Any] | None = None
    rollback_state: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=500)


class ExecutionResult(BaseModel):
    success: bool
    workflow: str
    repository: str
    workspace: str
    return_codes: dict[str, int] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error: str | None = None


class StepExecutionResult(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    success: bool
    return_code: int | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: float = Field(ge=0)
    timed_out: bool = False
    stdout_log: str = Field(min_length=1, max_length=250)
    stderr_log: str = Field(min_length=1, max_length=250)


class WorkflowExecutionResult(BaseModel):
    workflow: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)
    base_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    task_attempt: int = Field(ge=1)
    total_duration_seconds: float = Field(ge=0)
    steps: list[StepExecutionResult] = Field(max_length=50)
    success: bool
    heartbeat_failures: list[Annotated[str, Field(min_length=1, max_length=200)]] = (
        Field(
            default_factory=list,
            max_length=20,
        )
    )
    termination_reason: str | None = Field(default=None, max_length=100)
    worker_version: str = Field(default="unknown", min_length=1, max_length=100)
    artifacts: list[str] = Field(default_factory=list, max_length=20)
    retryable: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("summary")
    @classmethod
    def bounded_summary(cls, summary: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(summary, ensure_ascii=True, sort_keys=True)) > 16_384:
            raise ValueError("execution summary exceeds 16 KiB")
        return summary
