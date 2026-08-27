import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AutonomousAgendaItem(BaseModel):
    node_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    role: str = Field(min_length=1, max_length=100)
    expected_output_type: str = Field(min_length=1, max_length=100)


class AutonomousSessionBudget(BaseModel):
    max_tasks: int = Field(ge=1, le=64)
    max_total_attempts: int = Field(ge=1, le=256)
    max_duration_seconds: int = Field(ge=60, le=86400)
    max_reconciliations: int = Field(ge=1, le=1000)
    max_no_progress_reconciliations: int = Field(ge=1, le=100)
    max_worker_losses: int = Field(default=0, ge=0, le=10)


class AutonomousResearchSessionCreate(BaseModel):
    session_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    project: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1)
    task_graph_id: uuid.UUID
    agenda: list[AutonomousAgendaItem] = Field(min_length=1, max_length=64)
    budget: AutonomousSessionBudget
    stop_conditions: list[str] = Field(min_length=1, max_length=30)
    escalation_conditions: list[str] = Field(min_length=1, max_length=30)
    allowed_scope: list[str] = Field(min_length=1, max_length=50)
    authority: Literal["no_capital"] = "no_capital"
    may_approve: Literal[False] = False
    may_expand_scope: Literal[False] = False
    may_promote: Literal[False] = False
    created_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def unique_agenda(self):
        keys = [item.node_key for item in self.agenda]
        if len(keys) != len(set(keys)):
            raise ValueError("Agenda node keys must be unique.")
        if self.budget.max_tasks != len(self.agenda):
            raise ValueError("max_tasks must equal the frozen agenda size.")
        return self


class AutonomousSessionAction(BaseModel):
    actor: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=1, max_length=2000)


class AutonomousSessionCheckpoint(BaseModel):
    kind: Literal["progress", "no_progress", "conflict", "worker_loss"]
    actor: str = Field(min_length=1, max_length=150)
    node_key: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    detail: str = Field(min_length=1, max_length=4000)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AutonomousSessionCloseout(BaseModel):
    actor: str = Field(min_length=1, max_length=150)
    evaluation_route_id: uuid.UUID
    selection_audit_id: uuid.UUID
    dossier: dict
    dossier_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    retained_outcomes: list[Literal["positive", "negative", "invalid", "failed", "cancelled"]] = Field(min_length=1)


class AutonomousResearchSessionResponse(BaseModel):
    id: uuid.UUID
    session_key: str
    project: str
    objective: str
    task_graph_id: uuid.UUID
    task_graph_digest: str
    agenda: dict
    agenda_digest: str
    budget: dict
    budget_digest: str
    status: str
    reconcile_count: int
    no_progress_count: int
    worker_loss_count: int
    terminal_reason: dict
    closeout: dict
    created_by: str
    created_at: datetime
    activated_at: datetime | None
    completed_at: datetime | None
    events: list[dict]
