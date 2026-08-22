from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

GraphPredicate = Literal[
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


class GraphExplorerQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    mode: Literal["neighborhood", "paths", "subgraph"] = "neighborhood"
    target_id: Optional[uuid.UUID] = None  # noqa: UP045 - macOS Python 3.9
    predicates: list[GraphPredicate] = Field(default_factory=list, max_length=12)
    direction: Literal["outgoing", "incoming", "both"] = "both"
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=100, ge=1, le=100)
    project: Optional[str] = Field(  # noqa: UP045 - macOS Python 3.9
        default=None, pattern=r"^[a-z][a-z0-9._-]{0,99}$"
    )

    @model_validator(mode="after")
    def target_matches_mode(self) -> GraphExplorerQuery:
        if self.mode == "paths" and self.target_id is None:
            raise ValueError("target_id is required for path queries")
        return self
