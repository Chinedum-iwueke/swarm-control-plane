from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProposalAction = Literal[
    "create_task",
    "needs_clarification",
    "decline",
]
SupportedTaskType = Literal[
    "code_validation",
    "engineering_mission",
    "infrastructure_observation",
    "infrastructure_operation",
    "research_experiment",
    "research_memory_sync",
]

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_FORBIDDEN_KEYS = {
    "command",
    "commands",
    "shell",
    "script",
    "argv",
    "executable",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    project: str = Field(min_length=1, max_length=100)
    task_type: SupportedTaskType
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

    @field_validator("project")
    @classmethod
    def safe_project(cls, value: str) -> str:
        if not _SAFE_NAME.fullmatch(value):
            raise ValueError("project must use a safe repository-style name")
        return value

    @model_validator(mode="after")
    def forbid_execution_surface(self) -> ProposedTask:
        def inspect(value: object) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if str(key).lower() in _FORBIDDEN_KEYS:
                        raise ValueError("proposal contains an execution command surface")
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


class FounderProposalDocument(StrictModel):
    schema_version: Literal[1]
    summary: str = Field(min_length=10, max_length=1000)
    interpretation: str = Field(min_length=10, max_length=4000)
    recommended_action: ProposalAction
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    clarification_questions: list[str] = Field(default_factory=list, max_length=20)
    target_role: str | None = Field(default=None, max_length=150)
    target_role_reason: str | None = Field(default=None, max_length=1000)
    safety_constraints: list[str] = Field(default_factory=list, max_length=20)
    proposed_task: ProposedTask | None = None

    @model_validator(mode="after")
    def task_matches_action(self) -> FounderProposalDocument:
        if self.recommended_action == "create_task" and self.proposed_task is None:
            raise ValueError("create_task requires proposed_task")
        if self.recommended_action != "create_task" and self.proposed_task is not None:
            raise ValueError("only create_task may include proposed_task")
        return self


class FounderProposalCreate(StrictModel):
    lease_token: str = Field(min_length=1)
    proposal: FounderProposalDocument


class FounderProposalDecision(StrictModel):
    actor: str = Field(
        min_length=1,
        max_length=150,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    reason: str = Field(min_length=10, max_length=1000)


class FounderProposalResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    source_task_id: uuid.UUID
    planner_agent_id: uuid.UUID
    status: str
    proposal: FounderProposalDocument | dict[str, Any]
    proposal_digest: str
    decision_reason: str | None
    decided_by: str | None
    materialized_task_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
