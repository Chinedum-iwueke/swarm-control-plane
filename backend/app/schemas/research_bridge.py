from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


BridgeState = Literal[
    "awaiting_approval", "approved", "registry_bound", "executed",
    "truth_validated", "bundle_finalized", "independently_reviewed",
    "published", "memory_confirmed", "complete",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernedResearchProposal(StrictModel):
    schema_version: Literal["governed-research-bridge-v1.0.0"]
    state: Literal["awaiting_approval"]
    authority: dict[str, Literal["prohibited"]]
    source: dict[str, Any]
    resolution: dict[str, Any]
    dataset: dict[str, Any]
    search: dict[str, Any]
    required_gates: list[str]
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def authority_is_bounded(self):
        required = {"capital", "live_orders", "self_approval", "production_promotion"}
        if set(self.authority) != required:
            raise ValueError("proposal must declare every no-capital authority boundary")
        if self.search.get("stopping_rule") != "exhaustive":
            raise ValueError("only exhaustive registered search is accepted")
        count = self.search.get("variant_count")
        limit = self.search.get("max_variants")
        if not isinstance(count, int) or not isinstance(limit, int) or count < 1 or count > limit:
            raise ValueError("proposal search budget is invalid")
        return self


class GovernedResearchBridgeCreate(StrictModel):
    proposal: GovernedResearchProposal


class GovernedResearchAdvance(StrictModel):
    expected_state: BridgeState
    next_state: BridgeState
    receipt: dict[str, Any]


class GovernedResearchBridgeResponse(StrictModel):
    id: UUID
    proposal_digest: str
    state: BridgeState
    proposal: dict
    receipts: dict
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
