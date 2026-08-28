from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EstimatorReceipt(StrictModel):
    estimator: Literal[
        "direct_method",
        "importance_sampling",
        "weighted_importance_sampling",
        "doubly_robust",
        "fitted_q_evaluation",
    ]
    point_estimate: float
    lower_confidence_bound: float
    upper_confidence_bound: float
    standard_error: float = Field(ge=0)
    effective_sample_size: float = Field(gt=0)
    maximum_importance_weight: float = Field(ge=1)
    estimate_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def interval_contains_estimate(self):
        if (
            not self.lower_confidence_bound
            <= self.point_estimate
            <= self.upper_confidence_bound
        ):
            raise ValueError("confidence interval must contain point estimate")
        return self


class StressReceipt(StrictModel):
    scenario: Literal[
        "adversarial_reward",
        "support_trimming",
        "importance_weight_clipping",
        "cost_expansion",
    ]
    lower_bound: float
    affected_fraction: float = Field(ge=0, le=1)
    receipt_digest: str = Field(pattern=_DIGEST)


class ProposalSupport(StrictModel):
    minimum_overlap: float = Field(ge=0, le=1)
    extrapolation_fraction: float = Field(ge=0, le=1)
    unsupported_actions: list[str] = Field(default_factory=list, max_length=1000)


class ConservativeGate(StrictModel):
    minimum_conservative_value: float
    minimum_effective_sample_size: float = Field(gt=0)
    minimum_overlap: float = Field(gt=0, le=1)
    maximum_extrapolation_fraction: float = Field(ge=0, lt=1)
    maximum_estimator_spread: float = Field(gt=0)
    maximum_importance_weight: float = Field(gt=1)
    required_stress_scenarios: list[
        Literal[
            "adversarial_reward",
            "support_trimming",
            "importance_weight_clipping",
            "cost_expansion",
        ]
    ] = Field(min_length=3, max_length=4)

    @model_validator(mode="after")
    def unique_stresses(self):
        if len(self.required_stress_scenarios) != len(
            set(self.required_stress_scenarios)
        ):
            raise ValueError("required stress scenarios must be unique")
        return self


class OffPolicyProposal(StrictModel):
    schema_version: Literal["conservative-off-policy-proposal-v1.0.0"]
    target_policy_key: str = Field(pattern=_KEY, max_length=180)
    target_policy_version: str = Field(pattern=_KEY, max_length=100)
    target_policy_digest: str = Field(pattern=_DIGEST)
    base_candidate_key: str = Field(pattern=_KEY, max_length=180)
    estimators: list[EstimatorReceipt] = Field(min_length=3, max_length=5)
    stresses: list[StressReceipt] = Field(min_length=3, max_length=4)
    support: ProposalSupport
    gate: ConservativeGate
    uncertainty_method: Literal["block_bootstrap", "studentized_bootstrap"]
    confidence_level: float = Field(gt=0.5, lt=1)
    reward_model_digest: str = Field(pattern=_DIGEST)
    independent_rebuild_digest: str = Field(pattern=_DIGEST)
    validation_environment: Literal["shadow"]
    deployment_authority: Literal[False] = False
    order_authority: Literal[False] = False
    capital_authority: Literal[False] = False

    @model_validator(mode="after")
    def complete_evidence(self):
        estimator_names = [item.estimator for item in self.estimators]
        stress_names = [item.scenario for item in self.stresses]
        if len(estimator_names) != len(set(estimator_names)):
            raise ValueError("estimator receipts must be unique")
        if len(stress_names) != len(set(stress_names)):
            raise ValueError("stress receipts must be unique")
        if not set(self.gate.required_stress_scenarios).issubset(stress_names):
            raise ValueError("all required stress scenarios need receipts")
        if self.reward_model_digest != self.independent_rebuild_digest:
            raise ValueError("independent reward model rebuild does not match")
        return self


class OffPolicyEvaluationCreate(StrictModel):
    evaluation_key: str = Field(pattern=_KEY, max_length=180)
    dataset_contract_id: UUID
    selection_audit_id: UUID
    calibration_assessment_id: UUID
    proposal: OffPolicyProposal
    proposal_digest: str = Field(pattern=_DIGEST)
    evaluated_by: str = Field(pattern=_KEY, max_length=150)


class OffPolicyEvaluationResponse(OffPolicyEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    evaluation: dict
    evaluation_digest: str
    decision: Literal["shadow_eligible", "rejected"]
    evaluated_at: datetime
