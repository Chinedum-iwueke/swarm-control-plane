from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.alpha_campaign import AlphaDatasetBinding

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlphaResearchBudget(StrictModel):
    maximum_cycles: int = Field(ge=1, le=168)
    maximum_hypotheses: int = Field(ge=2, le=500)
    maximum_total_trials: int = Field(ge=1, le=50_000)
    maximum_variants_per_hypothesis: int = Field(ge=1, le=256)
    maximum_candidates_per_cycle: int = Field(ge=2, le=20)
    cadence_seconds: int = Field(ge=60, le=86_400)
    maximum_consecutive_failures: int = Field(ge=1, le=20)


class AlphaResearchMandateCreate(StrictModel):
    mandate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    objective: str = Field(min_length=20, max_length=4000)
    valid_from: datetime
    valid_until: datetime
    bulletproof_source_commit: str = Field(pattern=_COMMIT)
    execution_window_start: datetime
    execution_window_end: datetime
    dataset_bindings: list[AlphaDatasetBinding] = Field(min_length=1, max_length=20)
    allowed_venues: list[Literal["bybit", "binance"]] = Field(
        min_length=1, max_length=2
    )
    allowed_instruments: list[str] = Field(min_length=1, max_length=50)
    minimum_liquidity_usd: float = Field(ge=0, le=10_000_000_000)
    budget: AlphaResearchBudget
    created_by: str = Field(pattern=_KEY, max_length=150)
    authority: Literal["no_capital_research"] = "no_capital_research"
    may_change_code: Literal[False] = False
    may_enter_shadow: Literal[False] = False
    may_place_orders: Literal[False] = False
    may_allocate_capital: Literal[False] = False
    may_self_evaluate: Literal[False] = False

    @model_validator(mode="after")
    def bounded_week(self):
        values = (
            self.valid_from,
            self.valid_until,
            self.execution_window_start,
            self.execution_window_end,
        )
        if any(item.tzinfo is None for item in values):
            raise ValueError("mandate and execution clocks must be timezone aware")
        if (
            self.valid_until <= self.valid_from
            or self.valid_until - self.valid_from > timedelta(days=7)
        ):
            raise ValueError(
                "research mandates must be positive and no longer than seven days"
            )
        if self.execution_window_end <= self.execution_window_start:
            raise ValueError("execution window must be increasing")
        normalized = [item.upper() for item in self.allowed_instruments]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed instruments must be unique")
        return self


class AlphaResearchMandateApproval(StrictModel):
    expected_mandate_digest: str = Field(pattern=_DIGEST)
    actor: Literal["founder-operator"]
    reason: str = Field(min_length=10, max_length=2000)


class AlphaFounderResearchIdeaCreate(StrictModel):
    mandate_id: uuid.UUID
    expected_mandate_digest: str = Field(pattern=_DIGEST)
    idea: str = Field(min_length=20, max_length=12000)
    submitted_by: Literal["founder-operator"]
    conversation_id: uuid.UUID | None = None
    minimum_history_days: int = Field(default=365, ge=365, le=3650)
    maximum_variants: int = Field(default=8, ge=1, le=8)
    universe_selection_policy: Literal["preregistered_point_in_time"] = (
        "preregistered_point_in_time"
    )
    universe_slices: list[Literal["stable", "volatile", "all_eligible"]] = Field(
        default_factory=lambda: ["stable", "volatile"], min_length=1, max_length=3
    )


class AlphaFounderResearchIdeaResponse(StrictModel):
    id: uuid.UUID
    mandate_id: uuid.UUID
    cycle_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    submitted_by: str
    idea: str
    constraints: dict
    idea_digest: str
    status: str
    created_at: datetime
    updated_at: datetime


class AlphaDiscoveryDataRequirement(StrictModel):
    venue: Literal["bybit", "binance"]
    instrument: str = Field(pattern=r"^[A-Z0-9_-]+$", max_length=50)
    timeframe: Literal["1m"]
    required_fields: list[str] = Field(min_length=1, max_length=50)
    minimum_history_observations: int = Field(ge=500, le=100_000_000)
    liquidity_floor_usd: float = Field(ge=0, le=10_000_000_000)


class AlphaDiscoveryParameterBudget(StrictModel):
    maximum_parameters: int = Field(ge=1, le=20)
    maximum_variants: int = Field(ge=1, le=256)
    parameter_names: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def names_fit_budget(self):
        if len(self.parameter_names) > self.maximum_parameters:
            raise ValueError("parameter names exceed the declared parameter budget")
        if len(self.parameter_names) != len(set(self.parameter_names)):
            raise ValueError("parameter names must be unique")
        return self


class AlphaEquationAssertion(StrictModel):
    expression: str = Field(min_length=1, max_length=4000)
    meaning: str = Field(min_length=10, max_length=4000)
    source_object_id: uuid.UUID
    source_content_digest: str = Field(pattern=_DIGEST)
    source_excerpt: str = Field(min_length=1, max_length=4000)
    verification: Literal[
        "source_replayed",
        "deterministically_verified",
        "independently_verified",
        "pending_independent_verification",
    ]
    verification_receipt_digest: str | None = Field(default=None, pattern=_DIGEST)

    @model_validator(mode="after")
    def verification_evidence(self):
        if (
            self.verification
            in {
                "deterministically_verified",
                "independently_verified",
            }
            and self.verification_receipt_digest is None
        ):
            raise ValueError(
                "verified equations require an immutable verification receipt"
            )
        return self


class AlphaPredictiveCandidate(StrictModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    title: str = Field(min_length=10, max_length=300)
    domain_key: str = Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=100)
    cluster_key: str = Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=100)
    question: str = Field(min_length=20, max_length=2000)
    predictor: str = Field(min_length=3, max_length=1000)
    target: str = Field(min_length=3, max_length=300)
    horizon: str = Field(min_length=2, max_length=100)
    causal_timing: str = Field(min_length=20, max_length=2000)
    null_hypothesis: str = Field(min_length=20, max_length=2000)
    predicted_direction: Literal["positive", "negative", "nonlinear", "conditional"]
    mechanism: str = Field(min_length=20, max_length=4000)
    rival_explanations: list[str] = Field(min_length=1, max_length=10)
    falsification_criteria: list[str] = Field(min_length=1, max_length=20)
    features: list[str] = Field(min_length=1, max_length=50)
    parameter_budget: AlphaDiscoveryParameterBudget
    data: AlphaDiscoveryDataRequirement
    evidence_object_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    evidence_digests: list[str] = Field(min_length=1, max_length=20)
    equations: list[AlphaEquationAssertion] = Field(default_factory=list, max_length=20)
    expected_information_gain: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def evidence_pairs(self):
        if len(self.evidence_object_ids) != len(self.evidence_digests):
            raise ValueError("evidence IDs and digests must be paired")
        return self


class AlphaResearchMandateResponse(StrictModel):
    id: uuid.UUID
    mandate_key: str
    version: str
    objective: str
    specification: dict
    budget: dict
    mandate_digest: str
    status: str
    cycle_count: int
    hypothesis_count: int
    trial_count: int
    created_by: str
    approved_by: str | None
    created_at: datetime
    valid_from: datetime
    valid_until: datetime
    approved_at: datetime | None
    heartbeat_at: datetime


class AlphaDiscoveryOverview(StrictModel):
    generated_at: datetime
    mandates: list[dict]
    cycles: list[dict]
    founder_ideas: list[dict]
    throughput: dict[str, int]
    stalls: list[dict]
    agents: list[dict]
    claim_boundary: str
