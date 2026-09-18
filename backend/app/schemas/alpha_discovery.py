from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.alpha_campaign import AlphaDatasetBinding

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_RESAMPLING_POLICY = "left_closed_left_labeled_complete_bars"
_LEGACY_RESAMPLING_POLICY = "right_closed_left_labeled_complete_bars"


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


class AlphaDiscoveryCatalogBinding(StrictModel):
    producer_receipt_id: uuid.UUID
    receipt_digest: str = Field(pattern=_DIGEST)
    source_commit: str = Field(pattern=_COMMIT)
    allowed_venues: list[Literal["bybit", "binance"]] = Field(
        min_length=1, max_length=2
    )
    selection_policy: Literal["point_in_time_pre_outcome"] = "point_in_time_pre_outcome"
    maximum_assets_per_hypothesis: int = Field(default=8, ge=1, le=20)


class AlphaReusableStrategy(StrictModel):
    hypothesis_id: str = Field(pattern=_KEY, max_length=180)
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=10, max_length=4000)
    hypothesis_family: str = Field(pattern=_KEY, max_length=180)
    strategy: str = Field(pattern=_KEY, max_length=180)
    input_mode: Literal["single_instrument", "aligned_basket"]
    maximum_instruments: int = Field(ge=1, le=20)
    signal_timeframes: list[str] = Field(min_length=1, max_length=20)
    variant_count: int = Field(ge=1, le=1_000_000)
    logging_requirements: list[str] = Field(max_length=200)
    reuse_blockers: list[str] = Field(max_length=50)
    bounded_weekly_reuse_eligible: bool
    contract_path: str = Field(
        pattern=r"^research/hypotheses/[A-Za-z0-9._-]+\.yaml$", max_length=300
    )
    contract_digest: str = Field(pattern=_DIGEST)


class AlphaStrategyCapabilityCatalog(StrictModel):
    schema_version: Literal["alpha-strategy-capability-catalog-v1.0.0"]
    source_commit: str = Field(pattern=_COMMIT)
    capabilities: list[AlphaReusableStrategy] = Field(min_length=1, max_length=200)
    capital_or_order_authority: Literal[False]
    claim_boundary: str = Field(min_length=20, max_length=2000)
    catalog_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def unique_capabilities(self):
        identities = [item.hypothesis_id for item in self.capabilities]
        if len(identities) != len(set(identities)):
            raise ValueError("strategy capability identities must be unique")
        return self


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
    discovery_catalog: AlphaDiscoveryCatalogBinding | None = None
    strategy_catalog: AlphaStrategyCapabilityCatalog
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


class AlphaDiscoveryGroundingRecovery(StrictModel):
    expected_mandate_digest: str = Field(pattern=_DIGEST)
    expected_cycle_id: uuid.UUID
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
        default_factory=lambda: ["all_eligible"], min_length=1, max_length=3
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
    instruments: list[str] = Field(default_factory=list, max_length=20)
    research_timeframe: str = Field(
        default="1m",
        pattern=r"^(?:[1-9][0-9]{0,3}m|[1-9][0-9]{0,2}h|[1-9][0-9]{0,2}d)$",
    )
    resampling_policy: Literal["left_closed_left_labeled_complete_bars"] = (
        _RESAMPLING_POLICY
    )
    required_fields: list[str] = Field(min_length=1, max_length=50)
    minimum_history_observations: int = Field(ge=500, le=100_000_000)
    liquidity_floor_usd: float = Field(ge=0, le=10_000_000_000)

    @field_validator("resampling_policy", mode="before")
    @classmethod
    def normalize_resampling_policy(cls, value):
        return _RESAMPLING_POLICY if value == _LEGACY_RESAMPLING_POLICY else value

    @model_validator(mode="after")
    def normalized_basket(self):
        instruments = self.instruments or [self.instrument]
        normalized = [item.upper() for item in instruments]
        if self.instrument not in normalized:
            raise ValueError("primary instrument must be included in the basket")
        if len(normalized) != len(set(normalized)):
            raise ValueError("basket instruments must be unique")
        if any(
            not item.replace("-", "").replace("_", "").isalnum() for item in normalized
        ):
            raise ValueError("basket instruments must be exchange-safe identifiers")
        self.instruments = normalized
        return self


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


class AlphaRepresentationPlan(StrictModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    venue: Literal["bybit", "binance"]
    instrument: str = Field(pattern=r"^[A-Z0-9_-]+$", max_length=50)
    instruments: list[str] = Field(min_length=1, max_length=20)
    source_timeframe: Literal["1m"]
    research_timeframe: str = Field(
        pattern=r"^(?:[1-9][0-9]{0,3}m|[1-9][0-9]{0,2}h|[1-9][0-9]{0,2}d)$"
    )
    resampling_policy: Literal["left_closed_left_labeled_complete_bars"]
    required_fields: list[str] = Field(min_length=1, max_length=50)
    minimum_history_observations: int = Field(ge=500, le=100_000_000)
    liquidity_floor_usd: float = Field(ge=0, le=10_000_000_000)
    transformation_rationale: str = Field(min_length=20, max_length=4000)
    rejected_alternatives: list[str] = Field(min_length=1, max_length=20)

    @field_validator("resampling_policy", mode="before")
    @classmethod
    def normalize_resampling_policy(cls, value):
        return _RESAMPLING_POLICY if value == _LEGACY_RESAMPLING_POLICY else value

    @model_validator(mode="after")
    def normalized_basket(self):
        self.instruments = [item.upper() for item in self.instruments]
        if self.instrument not in self.instruments:
            raise ValueError("primary instrument must be included in the basket")
        if len(self.instruments) != len(set(self.instruments)):
            raise ValueError("basket instruments must be unique")
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
    reusable_hypothesis_id: str | None = Field(
        default=None, pattern=_KEY, max_length=180
    )

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
