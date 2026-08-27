from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GraphTaskSpec(BaseModel):
    task_type: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1)
    input_contract: dict = Field(default_factory=dict)
    expected_outputs: list[str] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    allowed_machines: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=1, ge=1, le=10)
    risk_level: int = Field(default=0, ge=0, le=5)


class TaskGraphNodeCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    role: str = Field(min_length=1, max_length=100)
    node_type: Literal["work", "review", "decision", "publication", "compensation"] = "work"
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    input_type: str = Field(min_length=1, max_length=100)
    output_type: str = Field(min_length=1, max_length=100)
    task: GraphTaskSpec
    stop_conditions: list[str] = Field(min_length=1, max_length=20)
    compensation: GraphTaskSpec | None = None


class TaskGraphCreate(BaseModel):
    graph_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    project: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1)
    created_by: str = Field(min_length=1, max_length=150)
    max_nodes: int = Field(default=32, ge=1, le=64)
    max_total_attempts: int = Field(default=64, ge=1, le=256)
    max_duration_seconds: int = Field(default=3600, ge=60, le=86400)
    max_parallelism: int = Field(default=4, ge=1, le=16)
    nodes: list[TaskGraphNodeCreate] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_dag(self) -> TaskGraphCreate:
        if len(self.nodes) > self.max_nodes:
            raise ValueError("Node count exceeds max_nodes.")
        keys = [node.key for node in self.nodes]
        if len(set(keys)) != len(keys):
            raise ValueError("Node keys must be unique.")
        known = set(keys)
        if any(dep not in known for node in self.nodes for dep in node.depends_on):
            raise ValueError("Every dependency must name a node in this graph.")
        graph = {node.key: node.depends_on for node in self.nodes}
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError("Task graph contains a cycle.")
            if key in visited:
                return
            visiting.add(key)
            for dep in graph[key]:
                visit(dep)
            visiting.remove(key)
            visited.add(key)
        for key in keys:
            visit(key)
        if sum(node.task.max_attempts for node in self.nodes) > self.max_total_attempts:
            raise ValueError("Declared node attempts exceed graph budget.")
        return self


class TaskGraphAction(BaseModel):
    actor: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=1, max_length=2000)


class TaskGraphMessageCreate(BaseModel):
    node_key: str | None = None
    message_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    sender: str = Field(min_length=1, max_length=100)
    recipient: str = Field(min_length=1, max_length=100)
    payload: dict


class TaskGraphResponse(BaseModel):
    id: uuid.UUID
    graph_key: str
    project: str
    objective: str
    status: str
    schema_version: str
    manifest_digest: str
    max_nodes: int
    max_total_attempts: int
    max_duration_seconds: int
    max_parallelism: int
    terminal_reason: dict
    created_at: datetime
    activated_at: datetime | None
    deadline_at: datetime | None
    completed_at: datetime | None
    nodes: list[dict]
    messages: list[dict]
    events: list[dict]


class TaskGraphReconcileResponse(BaseModel):
    graph: TaskGraphResponse
    transitioned_nodes: int
    compensation_tasks_created: int
