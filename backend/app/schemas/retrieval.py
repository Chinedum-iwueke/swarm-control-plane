from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SCHEMA_VERSION = r"^canonical-evidence-v[0-9]+\.[0-9]+\.[0-9]+$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


RetrievalChannel = Literal["exact", "lexical", "vector", "graph"]
ScientificType = Literal[
    "section", "paragraph", "table", "figure", "equation", "citation", "note"
]


class HybridRetrievalRequest(StrictModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    project: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    scientific_types: list[ScientificType] = Field(default_factory=list, max_length=7)
    channels: list[RetrievalChannel] = Field(
        default_factory=lambda: ["exact", "lexical", "vector", "graph"],
        min_length=1,
        max_length=4,
    )
    compatible_schema_versions: list[str] = Field(
        default_factory=lambda: ["canonical-evidence-v1.0.0"],
        min_length=1,
        max_length=10,
    )
    projection_version: Literal["hybrid-retrieval-v1.0.0"] = "hybrid-retrieval-v1.0.0"
    fusion: Literal["rrf-v1"] = "rrf-v1"

    @field_validator("channels")
    @classmethod
    def channels_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("retrieval channels must be unique")
        return value

    @field_validator("compatible_schema_versions")
    @classmethod
    def versions_are_supported(cls, value: list[str]) -> list[str]:
        import re

        if len(set(value)) != len(value) or any(
            re.fullmatch(_SCHEMA_VERSION, item) is None for item in value
        ):
            raise ValueError("compatible schema versions are invalid")
        return value


class CitationCoordinates(StrictModel):
    page: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class RetrievalCitation(StrictModel):
    object_id: UUID
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    coordinates: CitationCoordinates
    replay_path: str


class HybridRetrievalHit(StrictModel):
    object_id: UUID
    project: str
    access_class: str
    object_schema_version: str
    scientific_type: ScientificType
    text: str
    score: float
    confidence: float = Field(ge=0, le=1)
    channel_scores: dict[RetrievalChannel, float]
    channel_ranks: dict[RetrievalChannel, int]
    citation: RetrievalCitation


class HybridRetrievalResponse(StrictModel):
    query: str
    projection_version: str
    corpus_digest: str
    fusion: Literal["rrf-v1"]
    stale: Literal[False]
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    calibration: Literal["evidence-confidence-v1"]
    hits: list[HybridRetrievalHit]


class ProjectionBuildResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    projection_name: Literal["canonical-scientific"]
    projection_version: Literal["hybrid-retrieval-v1.0.0"]
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_count: int = Field(ge=0)
    built_at: datetime


class ProjectionStatusResponse(ProjectionBuildResponse):
    stale: bool
    current_corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
