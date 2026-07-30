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


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: EngineeringMilestoneManifest
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
