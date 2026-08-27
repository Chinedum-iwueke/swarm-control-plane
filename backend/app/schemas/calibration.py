from __future__ import annotations

from datetime import datetime
from itertools import pairwise
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReliabilityBin(StrictModel):
    lower_probability: float = Field(ge=0, le=1)
    upper_probability: float = Field(gt=0, le=1)
    observations: int = Field(ge=1)
    mean_probability: float = Field(ge=0, le=1)
    observed_frequency: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def boundaries(self):
        if self.upper_probability <= self.lower_probability:
            raise ValueError("reliability bin bounds must increase")
        if (
            not self.lower_probability
            <= self.mean_probability
            <= self.upper_probability
        ):
            raise ValueError("mean probability must lie inside its bin")
        return self


class UncertaintyContract(StrictModel):
    method: Literal["split_conformal", "block_bootstrap"]
    nominal_coverage: float = Field(gt=0.5, lt=1)
    empirical_coverage: float = Field(ge=0, le=1)
    mean_interval_width: float = Field(gt=0, le=1)
    calibration_sample_digest: str = Field(pattern=_DIGEST)


class ApplicabilitySlice(StrictModel):
    slice_key: str = Field(pattern=_KEY, max_length=120)
    observations: int = Field(ge=1)
    calibration_error: float = Field(ge=0, le=1)
    shift_distance: float = Field(ge=0)
    supported: bool


class ExplanationContract(StrictModel):
    method: Literal["linear_coefficients", "permutation_importance", "shap"]
    explanation_digest: str = Field(pattern=_DIGEST)
    fidelity_score: float = Field(ge=0, le=1)
    stability_score: float = Field(ge=0, le=1)
    causal_claims_prohibited: Literal[True] = True


class AbstentionPolicy(StrictModel):
    maximum_expected_calibration_error: float = Field(gt=0, le=0.5)
    minimum_empirical_coverage: float = Field(gt=0.5, le=1)
    maximum_shift_distance: float = Field(gt=0)
    minimum_support: int = Field(ge=20)
    maximum_uncertainty: float = Field(gt=0, le=1)
    minimum_explanation_fidelity: float = Field(gt=0, le=1)


class InferenceScenarioReceipt(StrictModel):
    scenario: Literal["supported", "miscalibrated", "distribution_shift", "low_support"]
    input_digest: str = Field(pattern=_DIGEST)
    probability: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    applicability: Literal["supported", "out_of_support"]
    support_count: int = Field(ge=0)
    shift_distance: float = Field(ge=0)
    expected_calibration_error: float = Field(ge=0, le=1)
    abstained: bool
    abstention_reason: Literal[
        "none", "miscalibrated", "distribution_shift", "low_support", "high_uncertainty"
    ]


class CalibrationSpecification(StrictModel):
    schema_version: Literal["calibration-uncertainty-abstention-v1.0.0"]
    calibration_version: str = Field(pattern=_KEY, max_length=100)
    calibration_method: Literal[
        "held_out_platt", "held_out_isotonic", "beta_calibration"
    ]
    reliability_bins: list[ReliabilityBin] = Field(min_length=5, max_length=100)
    uncertainty: UncertaintyContract
    applicability_slices: list[ApplicabilitySlice] = Field(min_length=2, max_length=100)
    explanation: ExplanationContract
    policy: AbstentionPolicy
    scenario_receipts: list[InferenceScenarioReceipt] = Field(
        min_length=4, max_length=20
    )
    action_authority: Literal[False] = False

    @model_validator(mode="after")
    def complete_contract(self):
        bins = sorted(self.reliability_bins, key=lambda item: item.lower_probability)
        if (
            bins != self.reliability_bins
            or bins[0].lower_probability != 0
            or bins[-1].upper_probability != 1
        ):
            raise ValueError("reliability bins must be ordered and span zero to one")
        if any(
            left.upper_probability != right.lower_probability
            for left, right in pairwise(bins)
        ):
            raise ValueError("reliability bins must be contiguous")
        scenarios = {item.scenario for item in self.scenario_receipts}
        if scenarios != {
            "supported",
            "miscalibrated",
            "distribution_shift",
            "low_support",
        }:
            raise ValueError(
                "all mandatory inference scenarios are required exactly once"
            )
        if len(scenarios) != len(self.scenario_receipts):
            raise ValueError("inference scenarios must be unique")
        return self


class CalibrationAssessmentCreate(StrictModel):
    assessment_key: str = Field(pattern=_KEY, max_length=180)
    evaluation_id: UUID
    dossier_id: UUID
    candidate_key: str = Field(pattern=_KEY, max_length=180)
    specification: CalibrationSpecification
    specification_digest: str = Field(pattern=_DIGEST)
    assessed_by: str = Field(pattern=_KEY, max_length=150)


class CalibrationAssessmentResponse(CalibrationAssessmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment: dict
    assessment_digest: str
    status: Literal["qualified", "demotion_required"]
    assessed_at: datetime
