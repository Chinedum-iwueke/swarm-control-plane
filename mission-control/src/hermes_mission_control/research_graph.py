from __future__ import annotations

import uuid
from datetime import datetime
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
    "mentions",
]


class GraphExplorerQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["canonical", "private"] = "canonical"
    root_ids: list[str] = Field(min_length=1, max_length=20)
    mode: Literal["neighborhood", "paths", "subgraph"] = "neighborhood"
    target_id: Optional[str] = None  # noqa: UP045 - macOS Python 3.9
    predicates: list[GraphPredicate] = Field(default_factory=list, max_length=12)
    direction: Literal["outgoing", "incoming", "both"] = "both"
    max_depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=100, ge=1, le=100)
    page_size: int = Field(default=50, ge=1, le=100)
    cursor: Optional[str] = Field(  # noqa: UP045 - macOS Python 3.9
        default=None, min_length=8, max_length=512
    )
    object_types: list[str] = Field(default_factory=list, max_length=20)
    as_of: Optional[datetime] = None  # noqa: UP045 - macOS Python 3.9
    project: Optional[str] = Field(  # noqa: UP045 - macOS Python 3.9
        default=None, pattern=r"^[a-z][a-z0-9._-]{0,99}$"
    )

    @model_validator(mode="after")
    def target_matches_mode(self) -> GraphExplorerQuery:
        if self.mode == "paths" and self.target_id is None:
            raise ValueError("target_id is required for path queries")
        if self.scope == "canonical":
            for item in self.root_ids:
                uuid.UUID(item)
            if self.target_id is not None:
                uuid.UUID(str(self.target_id))
            if "mentions" in self.predicates:
                raise ValueError("mentions is available only in the private graph")
        elif any(not _private_graph_id(item) for item in self.root_ids):
            raise ValueError("private graph roots must use opaque local identifiers")
        if self.scope == "private" and self.project not in {None, "local-private"}:
            raise ValueError("private graph queries are confined to local-private")
        if (
            self.scope == "private"
            and self.target_id is not None
            and not _private_graph_id(self.target_id)
        ):
            raise ValueError("private path targets must use opaque local identifiers")
        return self

    def canonical_payload(self) -> dict:
        return self.model_dump(
            mode="json",
            exclude={"scope"},
            exclude_none=True,
        )


def _private_graph_id(value: str) -> bool:
    return value.startswith(("private-source:", "private-entity:")) and (
        20 <= len(value) <= 96
    )
