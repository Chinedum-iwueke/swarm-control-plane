from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlphaCampaignBudget(StrictModel):
    max_hypotheses: int = Field(ge=1, le=100)
    max_total_trials: int = Field(ge=1, le=10_000)
    max_variants_per_hypothesis: int = Field(ge=1, le=256)
    max_duration_seconds: int = Field(ge=3600, le=2_592_000)
    max_consecutive_failures: int = Field(ge=1, le=20)


class AlphaDatasetBinding(StrictModel):
    dataset_build_id: uuid.UUID
    catalog_id: uuid.UUID
    lake_governance_snapshot_id: uuid.UUID
    producer_receipt_id: uuid.UUID
    dataset_key: str = Field(pattern=_KEY, max_length=150)
    partition_digests: list[str] = Field(min_length=1, max_length=10_000)
    evidence_class: Literal["live_exchange_history"]
    research_principal: Literal["alpha-research-runner"]

    @model_validator(mode="after")
    def unique_partitions(self):
        if len(self.partition_digests) != len(set(self.partition_digests)):
            raise ValueError("partition digests must be unique")
        if any(not re.fullmatch(_DIGEST, item) for item in self.partition_digests):
            raise ValueError("partition digests must be SHA-256 values")
        return self


class AlphaCampaignCreate(StrictModel):
    campaign_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    project: Literal["bulletproof-bt"]
    objective: str = Field(min_length=20, max_length=4000)
    discovery_portfolio_id: uuid.UUID
    dataset_bindings: list[AlphaDatasetBinding] = Field(min_length=1, max_length=20)
    bulletproof_source_commit: str = Field(pattern=_COMMIT)
    allowed_venues: list[Literal["bybit", "binance"]] = Field(
        min_length=1, max_length=2
    )
    allowed_instruments: list[str] = Field(min_length=1, max_length=50)
    budget: AlphaCampaignBudget
    created_by: str = Field(pattern=_KEY, max_length=150)
    authority: Literal["no_capital"] = "no_capital"
    may_self_approve: Literal[False] = False
    may_place_orders: Literal[False] = False
    may_promote_live: Literal[False] = False
    execution_protocol: (
        Literal["alpha002-native-v1", "alpha003-governed-v1", "alpha004-delegated-v1"]
        | None
    ) = None
    execution_window_start: datetime | None = None
    execution_window_end: datetime | None = None
    research_mandate_id: uuid.UUID | None = None
    research_mandate_digest: str | None = Field(default=None, pattern=_DIGEST)

    @model_validator(mode="after")
    def unique_scope(self):
        if len(self.allowed_venues) != len(set(self.allowed_venues)):
            raise ValueError("allowed venues must be unique")
        normalized = [item.upper() for item in self.allowed_instruments]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed instruments must be unique")
        if any(
            not item.replace("-", "").replace("_", "").isalnum() for item in normalized
        ):
            raise ValueError("allowed instruments must be exchange-safe identifiers")
        if self.execution_protocol in {
            "alpha003-governed-v1",
            "alpha004-delegated-v1",
        }:
            if self.execution_window_start is None or self.execution_window_end is None:
                raise ValueError("ALPHA-003 requires an immutable execution window")
            if self.execution_window_start >= self.execution_window_end:
                raise ValueError("execution window must be increasing")
        if self.execution_protocol == "alpha004-delegated-v1" and (
            self.research_mandate_id is None or self.research_mandate_digest is None
        ):
            raise ValueError("ALPHA-004 requires an immutable research mandate")
        return self


class AlphaCampaignActivation(StrictModel):
    expected_campaign_digest: str = Field(pattern=_DIGEST)
    actor: Literal["founder-operator", "alpha-continuous-director"]
    reason: str = Field(min_length=10, max_length=2000)


class AlphaGateReport(StrictModel):
    truth_certified: bool
    point_in_time_valid: bool
    reproducible: bool
    out_of_sample_evaluated: bool
    cost_stress_evaluated: bool
    selection_bias_audited: bool
    independent_review_complete: bool
    required_trade_logging_complete: bool | None = None
    execution_class: Literal["qualification", "commissioning"] | None = None
    qualification_authority: bool | None = None
    shadow_eligible: bool
    production_eligible: Literal[False] = False
    capital_authority: Literal[False] = False
    failed_gates: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def consistent(self):
        if self.execution_class == "commissioning" and self.qualification_authority is not False:
            raise ValueError("commissioning evidence cannot have qualification authority")
        if self.execution_class == "qualification" and self.qualification_authority is False:
            raise ValueError("qualification evidence must retain qualification authority")
        required = (
            self.truth_certified,
            self.point_in_time_valid,
            self.reproducible,
            self.out_of_sample_evaluated,
            self.cost_stress_evaluated,
            self.selection_bias_audited,
            self.independent_review_complete,
        )
        if self.shadow_eligible and (not all(required) or self.failed_gates):
            raise ValueError("shadow eligibility requires every no-capital gate")
        if self.shadow_eligible and self.required_trade_logging_complete is False:
            raise ValueError("shadow eligibility requires complete trade logging")
        if self.shadow_eligible and self.qualification_authority is False:
            raise ValueError("shadow eligibility requires qualification authority")
        return self


class AlphaCampaignAttemptCreate(StrictModel):
    attempt_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    expected_campaign_digest: str = Field(pattern=_DIGEST)
    question: str = Field(min_length=10, max_length=4000)
    question_digest: str = Field(pattern=_DIGEST)
    source_candidate_id: uuid.UUID
    source_candidate_digest: str = Field(pattern=_DIGEST)
    hypothesis_id: str = Field(pattern=_KEY, max_length=180)
    hypothesis_digest: str = Field(pattern=_DIGEST)
    dataset_build_id: uuid.UUID
    dataset_digest: str = Field(pattern=_DIGEST)
    governed_bridge_id: uuid.UUID | None = None
    trial_count: int = Field(ge=0, le=10_000)
    outcome: Literal["candidate", "negative", "invalid", "failed"]
    failure_stage: (
        Literal[
            "data_admission",
            "hypothesis_compilation",
            "strategy_generation",
            "execution",
            "truth_gate",
            "independent_evaluation",
        ]
        | None
    ) = None
    gate_report: AlphaGateReport
    evidence_digests: list[str] = Field(min_length=1, max_length=100)
    produced_by: Literal["bulletproof_bt"]
    source_commit: str = Field(pattern=_COMMIT)

    @model_validator(mode="after")
    def outcome_is_consistent(self):
        if self.outcome == "candidate":
            if self.governed_bridge_id is None or not self.gate_report.shadow_eligible:
                raise ValueError(
                    "candidate requires a complete bridge and shadow eligibility"
                )
            if self.failure_stage is not None:
                raise ValueError("candidate cannot declare a failure stage")
        elif self.gate_report.shadow_eligible:
            raise ValueError("non-candidates cannot be shadow eligible")
        if self.outcome == "failed" and self.failure_stage is None:
            raise ValueError("failed attempts require a failure stage")
        if self.outcome != "failed" and self.failure_stage is not None:
            raise ValueError("failure stage is only valid for failed attempts")
        if len(self.evidence_digests) != len(set(self.evidence_digests)):
            raise ValueError("evidence digests must be unique")
        return self


class AlphaCampaignAction(StrictModel):
    expected_campaign_digest: str = Field(pattern=_DIGEST)
    actor: str = Field(pattern=_KEY, max_length=150)
    reason: str = Field(min_length=10, max_length=2000)


class AlphaCampaignResponse(StrictModel):
    id: uuid.UUID
    campaign_key: str
    version: str
    project: str
    objective: str
    discovery_portfolio_id: uuid.UUID
    campaign_digest: str
    specification: dict
    budget: dict
    status: str
    phase: str
    next_action: str
    hypothesis_count: int
    trial_count: int
    consecutive_failures: int
    terminal_reason: dict
    candidate_attempt_id: uuid.UUID | None
    created_by: str
    created_at: datetime
    activated_at: datetime | None
    heartbeat_at: datetime
    completed_at: datetime | None
    attempts: list[dict]
    events: list[dict]
    execution: dict | None = None
    claim_boundary: str
