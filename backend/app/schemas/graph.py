from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccessClass = Literal["public", "internal", "restricted", "protected"]
EdgePredicate = Literal[
    "derived_from",
    "supersedes",
    "supports",
    "contradicts",
    "uses_method",
    "uses_dataset",
    "produced_result",
    "reviews",
    "decides_on",
    "belongs_to_trial_family",
    "depends_on",
    "cites",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalEdgeCreate(StrictModel):
    subject_id: UUID
    predicate: EdgePredicate
    object_id: UUID
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    provenance_object_id: UUID
    access_class: AccessClass
    created_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")

    @model_validator(mode="after")
    def validate_relation(self) -> CanonicalEdgeCreate:
        if self.subject_id == self.object_id:
            raise ValueError("self-referential canonical edges are not allowed")
        if self.valid_until is not None and (
            self.valid_from is None or self.valid_until <= self.valid_from
        ):
            raise ValueError("valid_until must be after valid_from")
        return self


class CanonicalEdgeResponse(CanonicalEdgeCreate):
    id: UUID
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class GraphProjectionResponse(StrictModel):
    projection_name: Literal["canonical-knowledge-graph"]
    projection_version: Literal["knowledge-graph-v1.0.0"]
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    built_at: datetime
    stale: bool = False


class GraphQueryRequest(StrictModel):
    root_ids: list[UUID] = Field(min_length=1, max_length=20)
    mode: Literal["neighborhood", "paths", "subgraph"] = "neighborhood"
    target_id: UUID | None = None
    predicates: list[EdgePredicate] = Field(default_factory=list, max_length=12)
    direction: Literal["outgoing", "incoming", "both"] = "both"
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=100, ge=1, le=500)
    as_of: datetime | None = None
    project: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9._-]{0,99}$")

    @model_validator(mode="after")
    def target_matches_mode(self) -> GraphQueryRequest:
        if self.mode == "paths" and self.target_id is None:
            raise ValueError("target_id is required for path queries")
        return self


class GraphNode(StrictModel):
    id: UUID
    object_type: str
    project: str
    access_class: AccessClass
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: str
    replay_path: str


class GraphEdge(StrictModel):
    id: UUID
    source: UUID
    target: UUID
    predicate: EdgePredicate
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    provenance_object_id: UUID
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class GraphQueryResponse(StrictModel):
    projection_version: str
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    paths: list[list[UUID]] = Field(default_factory=list)
    truncated: bool


class ContextPackRequest(StrictModel):
    query: str = Field(min_length=2, max_length=1000)
    object_ids: list[UUID] = Field(min_length=1, max_length=50)
    purpose: str = Field(min_length=2, max_length=300)
    max_items: int = Field(default=20, ge=1, le=50)


class ContextPackResponse(StrictModel):
    schema_version: Literal["citation-context-pack-v1.0.0"]
    query: str
    purpose: str
    items: list[dict]
    graph_query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_pack_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CognitiveToolRequest(StrictModel):
    tool: Literal["mean", "sample-standard-deviation", "sharpe", "max-drawdown"]
    values: list[float] = Field(min_length=1, max_length=100_000)
    parameters: dict[str, int | float | str] = Field(default_factory=dict)
    context_pack_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def parameters_match_tool(self) -> CognitiveToolRequest:
        allowed = (
            {"risk_free_rate", "periods_per_year"} if self.tool == "sharpe" else set()
        )
        if set(self.parameters) - allowed:
            raise ValueError("parameters are not supported by the selected tool")
        periods = self.parameters.get("periods_per_year", 1)
        if not isinstance(periods, (int, float)) or periods <= 0:
            raise ValueError("periods_per_year must be positive")
        return self


class CognitiveToolResponse(StrictModel):
    receipt_id: UUID
    tool: str
    tool_version: Literal["deterministic-scientific-tools-v1.0.0"]
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: dict[str, int | float | str | None]
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_pack_digest: str | None = None
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
