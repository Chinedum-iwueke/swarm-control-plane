from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BehaviorPolicyContract(StrictModel):
    policy_key: str = Field(pattern=_KEY, max_length=180)
    policy_version: str = Field(pattern=_KEY, max_length=100)
    policy_digest: str = Field(pattern=_DIGEST)
    propensity_source: Literal["logged", "deterministically_reconstructed"]
    minimum_allowed_propensity: float = Field(gt=0, le=1)
    deterministic: bool


class ActionDefinition(StrictModel):
    action_key: str = Field(pattern=_KEY, max_length=120)
    kind: Literal["discrete", "continuous"]
    unit: str = Field(pattern=_KEY, max_length=80)
    lower_bound: float
    upper_bound: float

    @model_validator(mode="after")
    def increasing_bounds(self):
        if self.upper_bound <= self.lower_bound:
            raise ValueError("action upper bound must exceed lower bound")
        return self


class StateFeature(StrictModel):
    feature_key: str = Field(pattern=_KEY, max_length=150)
    availability_lag_steps: int = Field(ge=0, le=1_000_000)
    source_digest: str = Field(pattern=_DIGEST)


class RewardContract(StrictModel):
    reward_key: str = Field(pattern=_KEY, max_length=150)
    formula: str = Field(min_length=3, max_length=2000)
    horizon_steps: int = Field(ge=1, le=1_000_000)
    availability_lag_steps: int = Field(ge=1, le=1_000_000)
    reward_digest: str = Field(pattern=_DIGEST)
    independent_rebuild_digest: str = Field(pattern=_DIGEST)
    clipping: Literal["none", "symmetric", "winsorized"]

    @model_validator(mode="after")
    def causal_and_reproducible(self):
        if self.availability_lag_steps < self.horizon_steps:
            raise ValueError("reward cannot be available before its horizon ends")
        if self.reward_digest != self.independent_rebuild_digest:
            raise ValueError("independent reward rebuild does not match")
        return self


class ConfounderDeclaration(StrictModel):
    confounder_key: str = Field(pattern=_KEY, max_length=150)
    status: Literal["observed", "proxy", "unobserved"]
    mitigation: str = Field(min_length=5, max_length=1000)


class ActionSupport(StrictModel):
    action_key: str = Field(pattern=_KEY, max_length=120)
    observations: int = Field(ge=0)
    minimum_propensity: float = Field(ge=0, le=1)
    maximum_importance_weight: float = Field(ge=1)


class DatasetAuditSummary(StrictModel):
    transition_count: int = Field(ge=1)
    episode_count: int = Field(ge=1)
    action_support: list[ActionSupport] = Field(min_length=2, max_length=1000)
    duplicate_transition_count: int = Field(ge=0)
    out_of_order_transition_count: int = Field(ge=0)
    state_availability_violation_count: int = Field(ge=0)
    reward_availability_violation_count: int = Field(ge=0)
    missing_propensity_count: int = Field(ge=0)
    terminal_transition_count: int = Field(ge=1)


class OfflineEvaluationProtocol(StrictModel):
    estimators: list[
        Literal[
            "direct_method",
            "importance_sampling",
            "weighted_importance_sampling",
            "doubly_robust",
            "fitted_q_evaluation",
        ]
    ] = Field(min_length=2, max_length=5)
    minimum_action_support: int = Field(ge=20)
    maximum_importance_weight: float = Field(gt=1)
    confidence_level: float = Field(gt=0.5, lt=1)
    unsupported_action_policy: Literal["abstain"]
    model_selection_dataset: Literal["separate_from_evaluation"]
    action_authority: Literal[False] = False
    capital_authority: Literal[False] = False

    @model_validator(mode="after")
    def unique_estimators(self):
        if len(self.estimators) != len(set(self.estimators)):
            raise ValueError("offline estimators must be unique")
        return self


class OfflineRLDatasetSpecification(StrictModel):
    schema_version: Literal["offline-rl-dataset-contract-v1.0.0"]
    shadow_journal_digest: str = Field(pattern=_DIGEST)
    shadow_replay_digest: str = Field(pattern=_DIGEST)
    shadow_journal_sealed: Literal[True]
    shadow_capital_or_order_authority: Literal[False]
    transition_schema_version: str = Field(pattern=_KEY, max_length=100)
    episode_definition: str = Field(min_length=10, max_length=2000)
    behavior_policy: BehaviorPolicyContract
    state_features: list[StateFeature] = Field(min_length=1, max_length=5000)
    actions: list[ActionDefinition] = Field(min_length=2, max_length=1000)
    reward: RewardContract
    confounders: list[ConfounderDeclaration] = Field(min_length=1, max_length=1000)
    audit_summary: DatasetAuditSummary
    evaluation: OfflineEvaluationProtocol

    @model_validator(mode="after")
    def identities_are_complete(self):
        action_keys = [item.action_key for item in self.actions]
        support_keys = [item.action_key for item in self.audit_summary.action_support]
        feature_keys = [item.feature_key for item in self.state_features]
        confounder_keys = [item.confounder_key for item in self.confounders]
        if len(action_keys) != len(set(action_keys)):
            raise ValueError("action identities must be unique")
        if set(action_keys) != set(support_keys) or len(support_keys) != len(
            set(support_keys)
        ):
            raise ValueError("action support must cover every action exactly once")
        if len(feature_keys) != len(set(feature_keys)):
            raise ValueError("state feature identities must be unique")
        if len(confounder_keys) != len(set(confounder_keys)):
            raise ValueError("confounder identities must be unique")
        return self


class OfflineRLDatasetCreate(StrictModel):
    contract_key: str = Field(pattern=_KEY, max_length=180)
    dataset_build_id: UUID
    contract: OfflineRLDatasetSpecification
    contract_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_KEY, max_length=150)


class OfflineRLDatasetResponse(OfflineRLDatasetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audit: dict
    audit_digest: str
    status: Literal["qualified", "quarantined"]
    registered_at: datetime
