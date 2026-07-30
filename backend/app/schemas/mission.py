import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SAFE = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
_PATH = r"^[A-Za-z0-9][A-Za-z0-9/_.-]*$"


class MissionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int = Field(ge=1, le=20)
    max_attempts_per_task: int = Field(ge=1, le=5)
    max_duration_seconds: int = Field(ge=60, le=86400)
    max_files_changed: int = Field(ge=1, le=100)
    max_diff_lines: int = Field(ge=1, le=10000)


class EngineeringWorkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=_SAFE, max_length=100)
    objective: str = Field(min_length=10, max_length=4000)
    depends_on: list[str] = Field(max_length=20)
    allowed_paths: list[str] = Field(min_length=1, max_length=50)
    context_paths: list[str] = Field(max_length=50)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=50)
    stop_conditions: list[str] = Field(min_length=1, max_length=20)

    @field_validator("allowed_paths", "context_paths")
    @classmethod
    def safe_paths(cls, paths: list[str]) -> list[str]:
        if any(
            path.startswith(("/", ".", "-"))
            or ".." in path.split("/")
            or not __import__("re").fullmatch(_PATH, path)
            for path in paths
        ):
            raise ValueError("paths must be safe repository-relative paths")
        return paths


class EngineeringMilestoneManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    milestone_id: str = Field(pattern=_SAFE, max_length=100)
    project: str = Field(pattern=_SAFE, max_length=100)
    objective: str = Field(min_length=10, max_length=4000)
    base_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    source_references: list[str] = Field(min_length=1, max_length=20)
    workflow: Literal["engineering-mission"]
    risk_level: int = Field(ge=0, le=1)
    allowed_machines: list[str] = Field(min_length=1, max_length=10)
    required_capabilities: list[str] = Field(min_length=1, max_length=20)
    budget: MissionBudget
    work_items: list[EngineeringWorkItem] = Field(min_length=1, max_length=20)
    deliverables: list[str] = Field(min_length=1, max_length=20)
    approved_by: str = Field(pattern=_SAFE, max_length=150)
    approval_reference: str = Field(pattern=_SAFE, max_length=200)

    @model_validator(mode="after")
    def valid_dag(self) -> "EngineeringMilestoneManifest":
        ids = [item.id for item in self.work_items]
        if len(ids) != len(set(ids)):
            raise ValueError("work item IDs must be unique")
        known = set(ids)
        if any(dep not in known for item in self.work_items for dep in item.depends_on):
            raise ValueError("dependency references an unknown work item")
        if any(item.id in item.depends_on for item in self.work_items):
            raise ValueError("work item cannot depend on itself")
        visiting: set[str] = set()
        visited: set[str] = set()
        graph = {item.id: item.depends_on for item in self.work_items}

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("work item dependencies contain a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for item_id in ids:
            visit(item_id)
        if len(ids) > self.budget.max_tasks:
            raise ValueError("work item count exceeds mission budget")
        return self


class InfrastructureMissionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tasks: int = Field(ge=1, le=20)
    max_attempts_per_task: int = Field(ge=1, le=3)
    max_duration_seconds: int = Field(ge=60, le=86400)


class InfrastructurePhase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=_SAFE, max_length=100)
    operation: Literal[
        "preflight-invariance-postgres",
        "stage-invariance-postgres",
        "start-invariance-postgres-private",
        "initialize-invariance-schema",
        "configure-invariance-backups",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
    ]
    objective: str = Field(min_length=10, max_length=4000)
    depends_on: list[str] = Field(max_length=20)
    risk_level: int = Field(ge=0, le=3)
    approval_required: bool
    acceptance_criteria: list[str] = Field(min_length=1, max_length=30)
    expected_outputs: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def operation_policy_matches(self) -> "InfrastructurePhase":
        expected = {
            "preflight-invariance-postgres": (0, False),
            "stage-invariance-postgres": (2, True),
            "start-invariance-postgres-private": (3, True),
            "initialize-invariance-schema": (3, True),
            "configure-invariance-backups": (3, True),
            "verify-invariance-postgres": (0, False),
            "prepare-invariance-cutover": (0, False),
        }[self.operation]
        if (self.risk_level, self.approval_required) != expected:
            raise ValueError("phase risk or approval policy is invalid")
        return self


class InfrastructureRunbookManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    milestone_id: str = Field(pattern=_SAFE, max_length=100)
    project: Literal["invariance_research"]
    objective: str = Field(min_length=10, max_length=4000)
    source_references: list[str] = Field(min_length=1, max_length=20)
    workflow: Literal["infrastructure-runbook"]
    runbook: Literal["vm2-postgres-deployment"]
    runbook_version: Literal["1.0.0"]
    target: Literal["vm2-invariance-postgres"]
    allowed_machines: list[str] = Field(min_length=1, max_length=1)
    required_capabilities: list[str] = Field(min_length=4, max_length=4)
    budget: InfrastructureMissionBudget
    phases: list[InfrastructurePhase] = Field(min_length=1, max_length=20)
    approved_by: str = Field(pattern=_SAFE, max_length=150)
    approval_reference: str = Field(pattern=_SAFE, max_length=200)

    @model_validator(mode="after")
    def valid_dag(self) -> "InfrastructureRunbookManifest":
        if self.allowed_machines != ["vm2-deployment"]:
            raise ValueError("infrastructure mission machine is invalid")
        if self.required_capabilities != [
            "deployment-architecture",
            "infrastructure-observation",
            "postgres-deployment",
            "service-health",
        ]:
            raise ValueError("infrastructure mission capabilities are invalid")
        ids = [phase.id for phase in self.phases]
        if len(ids) != len(set(ids)):
            raise ValueError("phase IDs must be unique")
        known = set(ids)
        graph = {phase.id: phase.depends_on for phase in self.phases}
        if any(dep not in known for deps in graph.values() for dep in deps):
            raise ValueError("dependency references an unknown phase")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("phase dependencies contain a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for phase_id in ids:
            visit(phase_id)
        if len(ids) > self.budget.max_tasks:
            raise ValueError("phase count exceeds mission budget")
        return self


MissionManifest = EngineeringMilestoneManifest | InfrastructureRunbookManifest


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: MissionManifest
    created_by: str = Field(pattern=_SAFE, max_length=150)
    approval_signature: str = Field(pattern=r"^[0-9a-f]{64}$")


class MissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    milestone_id: str
    project: str
    objective: str
    status: str
    manifest_digest: str
    manifest: dict
    approved_by: str
    approval_reference: str
    approval_signature: str
    max_tasks: int
    max_attempts: int
    max_duration_seconds: int
    deadline_at: datetime
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class MissionDetailResponse(BaseModel):
    mission: MissionResponse
    tasks: list[dict]
    dependencies: list[dict]
    events: list[dict]
