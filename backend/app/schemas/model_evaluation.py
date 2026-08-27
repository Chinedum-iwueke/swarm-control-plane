from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationProtocol(StrictModel):
    schema_version: Literal["model-family-regime-evaluation-v1.0.0"]
    primary_metric: Literal["balanced_accuracy", "net_information_coefficient"]
    minimum_incremental_value: float = Field(gt=0, le=1)
    minimum_regime_score: float = Field(ge=-1, le=1)
    maximum_regime_dispersion: float = Field(gt=0, le=2)
    maximum_permutation_score: float = Field(ge=-1, le=1)
    minimum_regime_observations: int = Field(ge=20, le=1_000_000)
    minimum_minority_fraction: float = Field(gt=0, le=0.5)
    required_regimes: list[str] = Field(min_length=2, max_length=100)
    action_authority: Literal[False] = False

    @model_validator(mode="after")
    def unique_regimes(self):
        if len(self.required_regimes) != len(set(self.required_regimes)):
            raise ValueError("required regimes must be unique")
        return self


class FoldMetric(StrictModel):
    fold: int = Field(ge=1)
    observations: int = Field(ge=1)
    primary_score: float = Field(ge=-1, le=1)
    log_loss: float = Field(ge=0)
    brier_score: float = Field(ge=0, le=1)


class RegimeMetric(StrictModel):
    regime: str = Field(pattern=_KEY, max_length=100)
    observations: int = Field(ge=1)
    positive_labels: int = Field(ge=0)
    negative_labels: int = Field(ge=0)
    primary_score: float = Field(ge=-1, le=1)

    @model_validator(mode="after")
    def counts_match(self):
        if self.positive_labels + self.negative_labels != self.observations:
            raise ValueError("regime label counts must equal observations")
        return self


class ModelCandidateEvaluation(StrictModel):
    candidate_key: str = Field(pattern=_KEY, max_length=180)
    family: Literal["baseline", "supervised", "unsupervised", "regime", "meta_label"]
    baseline_kind: Literal["unconditional", "linear"] | None = None
    model_bundle_digest: str = Field(pattern=_DIGEST)
    predictions_digest: str = Field(pattern=_DIGEST)
    overall_primary_score: float = Field(ge=-1, le=1)
    permutation_primary_score: float = Field(ge=-1, le=1)
    fold_metrics: list[FoldMetric] = Field(min_length=1, max_length=1000)
    regime_metrics: list[RegimeMetric] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def family_contract(self):
        if self.family == "baseline" and self.baseline_kind is None:
            raise ValueError("baseline candidates require baseline_kind")
        if self.family != "baseline" and self.baseline_kind is not None:
            raise ValueError("only baseline candidates may declare baseline_kind")
        if len({item.fold for item in self.fold_metrics}) != len(self.fold_metrics):
            raise ValueError("candidate fold identities must be unique")
        if len({item.regime for item in self.regime_metrics}) != len(
            self.regime_metrics
        ):
            raise ValueError("candidate regime identities must be unique")
        return self


class ModelFamilyEvaluationCreate(StrictModel):
    evaluation_key: str = Field(pattern=_KEY, max_length=180)
    materialization_id: UUID
    selection_audit_id: UUID
    protocol: EvaluationProtocol
    protocol_digest: str = Field(pattern=_DIGEST)
    candidates: list[ModelCandidateEvaluation] = Field(min_length=5, max_length=1000)
    candidates_digest: str = Field(pattern=_DIGEST)
    evaluated_by: str = Field(pattern=_KEY, max_length=150)


class ModelFamilyEvaluationResponse(ModelFamilyEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scorecard: dict
    scorecard_digest: str
    evaluated_at: datetime
