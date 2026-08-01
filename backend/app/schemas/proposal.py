from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

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


class ProposedTask(StrictModel):
    project: str = Field(min_length=1, max_length=100)
    task_type: SupportedTaskType
    title: str = Field(min_length=3, max_length=300)
    objective: str = Field(min_length=10, max_length=8000)
    priority: int = Field(default=50, ge=0, le=100)
    risk_level: int = Field(default=0, ge=0, le=5)
    input_contract: dict = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list, max_length=30)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=30)
    approval_policy: dict = Field(default_factory=dict)
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
    proposal: FounderProposalDocument
    proposal_digest: str
    decision_reason: str | None
    decided_by: str | None
    materialized_task_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
