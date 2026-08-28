from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DrawdownPath(StrictModel):
    maximum_drawdown: float = Field(ge=0, le=1)
    maximum_duration_periods: int = Field(ge=0)
    recovery_duration_periods: int | None = Field(default=None, ge=0)
    underwater_path_digest: str = Field(pattern=_DIGEST)


class TailEstimate(StrictModel):
    confidence_level: float = Field(gt=0.5, lt=1)
    value_at_risk: float = Field(ge=0, le=1)
    expected_shortfall: float = Field(ge=0, le=1)
    expected_shortfall_upper_bound: float = Field(ge=0, le=1)
    method: Literal["block_bootstrap", "filtered_historical", "evt"]
    sample_size: int = Field(ge=100)
    receipt_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def ordered_tail(self):
        if self.expected_shortfall < self.value_at_risk:
            raise ValueError("expected shortfall must be at least value at risk")
        if self.expected_shortfall_upper_bound < self.expected_shortfall:
            raise ValueError("tail upper bound must contain expected shortfall")
        return self


ScenarioKind = Literal[
    "price_gap",
    "correlation_break",
    "liquidity_freeze",
    "model_failure",
    "prolonged_drawdown",
]


class StressScenario(StrictModel):
    scenario: ScenarioKind
    version: str = Field(pattern=_KEY, max_length=100)
    source_digest: str = Field(pattern=_DIGEST)
    loss_fraction: float = Field(ge=0, le=1)
    uncertainty_upper_bound: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def uncertainty_contains_loss(self):
        if self.uncertainty_upper_bound < self.loss_fraction:
            raise ValueError("scenario uncertainty must contain loss")
        return self


class ReverseStress(StrictModel):
    scenario: ScenarioKind
    breach_limit: float = Field(gt=0, le=1)
    last_safe_shock: float = Field(ge=0)
    first_breaching_shock: float = Field(gt=0)
    loss_at_breach: float = Field(gt=0, le=1)
    method: Literal["bounded_bisection", "monotone_grid"]
    receipt_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def valid_bracket(self):
        if self.first_breaching_shock <= self.last_safe_shock:
            raise ValueError("reverse stress must bracket the first breach")
        if self.loss_at_breach < self.breach_limit:
            raise ValueError("reverse stress breach must reach its limit")
        return self


class RiskLimits(StrictModel):
    maximum_drawdown: float = Field(gt=0, le=1)
    maximum_tail_loss: float = Field(gt=0, le=1)
    maximum_scenario_loss: float = Field(gt=0, le=1)
    maximum_evidence_age_seconds: int = Field(gt=0)


class RiskStressRequest(StrictModel):
    schema_version: Literal["risk-stress-request-v1.0.0"]
    portfolio_candidate_key: str = Field(pattern=_KEY, max_length=180)
    candidate_digest: str = Field(pattern=_DIGEST)
    portfolio_state_digest: str = Field(pattern=_DIGEST)
    bulletproof_run_digest: str = Field(pattern=_DIGEST)
    cost_model_digest: str = Field(pattern=_DIGEST)
    scenario_pack_version: str = Field(pattern=_KEY, max_length=100)
    scenario_pack_digest: str = Field(pattern=_DIGEST)
    evidence_age_seconds: int = Field(ge=0)
    drawdown: DrawdownPath
    tail: TailEstimate
    scenarios: list[StressScenario] = Field(min_length=5, max_length=5)
    reverse_stresses: list[ReverseStress] = Field(min_length=5, max_length=5)
    limits: RiskLimits
    validation_environment: Literal["historical", "shadow"]
    allocation_authority: Literal[False] = False
    order_authority: Literal[False] = False
    capital_authority: Literal[False] = False

    @model_validator(mode="after")
    def complete_scenarios(self):
        required = {
            "price_gap",
            "correlation_break",
            "liquidity_freeze",
            "model_failure",
            "prolonged_drawdown",
        }
        scenarios = [item.scenario for item in self.scenarios]
        reverse = [item.scenario for item in self.reverse_stresses]
        if set(scenarios) != required or len(scenarios) != len(set(scenarios)):
            raise ValueError("all five unique stress scenarios are required")
        if set(reverse) != required or len(reverse) != len(set(reverse)):
            raise ValueError("all five unique reverse stresses are required")
        return self


class RiskStressAssessmentCreate(StrictModel):
    assessment_key: str = Field(pattern=_KEY, max_length=180)
    request: RiskStressRequest
    request_digest: str = Field(pattern=_DIGEST)
    assessed_by: str = Field(pattern=_KEY, max_length=150)


class RiskStressAssessmentResponse(RiskStressAssessmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_digest: str
    scenario_pack_digest: str
    dossier: dict
    dossier_digest: str
    decision: Literal["admissible", "blocked"]
    assessed_at: datetime
