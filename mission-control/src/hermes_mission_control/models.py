from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntakeRequest(StrictModel):
    kind: Literal["task", "mission"]
    project: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    title: str = Field(min_length=3, max_length=160)
    objective: str = Field(min_length=10, max_length=4000)
    risk_level: int = Field(default=0, ge=0, le=5)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)


class ConversationCreateRequest(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=1, max_length=12000)


class ConversationTurnRequest(StrictModel):
    message: str = Field(min_length=1, max_length=12000)


class ConversationTransitionRequest(StrictModel):
    action: Literal["finish", "stop", "resume", "archive"]
    reason: str = Field(min_length=3, max_length=500)


class ApprovalDecision(StrictModel):
    reason: str = Field(min_length=10, max_length=500)
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)


class ProposalDecision(StrictModel):
    reason: str = Field(min_length=10, max_length=1000)


class KnowledgeIngestRequest(StrictModel):
    path: str = Field(min_length=1, max_length=2000)
    confidentiality: Literal["private", "internal"] = "private"


class KnowledgeSearchResult(StrictModel):
    source_id: int
    title: str
    path: str
    digest: str
    modified_at: str
    line_start: int
    line_end: int
    excerpt: str
    score: float
    citation: str


class KnowledgeIngestResult(StrictModel):
    source_id: int
    title: str
    path: str
    digest: str
    chunks: int
    entities: int
    unchanged: bool


class GraphNode(StrictModel):
    id: int
    name: str
    kind: str


class GraphEdge(StrictModel):
    source: int
    target: int
    relation: str


class KnowledgeGraph(StrictModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ApprovalAction(StrictModel):
    approval_id: UUID
    action: Literal["approve", "reject"]
    reason: str
