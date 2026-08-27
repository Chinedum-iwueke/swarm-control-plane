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


class FeatureBinding(StrictModel):
    feature_key: str = Field(pattern=_KEY, max_length=150)
    factor_key: str = Field(pattern=_KEY, max_length=150)
    availability_lag_bars: int = Field(ge=1, le=1_000_000)
    missing_policy: Literal["drop", "preserve"]


class LabelContract(StrictModel):
    label_key: str = Field(pattern=_KEY, max_length=150)
    kind: Literal["forward_return", "forward_direction", "triple_barrier"]
    horizon_bars: int = Field(ge=1, le=1_000_000)
    label_end_offset_bars: int = Field(ge=1, le=1_000_000)

    @model_validator(mode="after")
    def end_covers_horizon(self):
        if self.label_end_offset_bars < self.horizon_bars:
            raise ValueError("label_end_offset_bars must cover the label horizon")
        return self


class FittedTransform(StrictModel):
    transform_key: str = Field(pattern=_KEY, max_length=150)
    kind: Literal["standardize", "winsorize", "impute", "rank"]
    fit_scope: Literal["train_only"]


class WalkForwardFold(StrictModel):
    fold: int = Field(ge=1, le=10_000)
    train_start: int = Field(ge=0)
    train_end: int = Field(gt=0)
    validation_start: int = Field(gt=0)
    validation_end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if not (
            self.train_start
            < self.train_end
            < self.validation_start
            < self.validation_end
        ):
            raise ValueError("fold intervals must be ordered and non-empty")
        return self


class SplitContract(StrictModel):
    method: Literal["expanding_walk_forward"]
    purge_bars: int = Field(ge=1, le=1_000_000)
    embargo_bars: int = Field(ge=1, le=1_000_000)
    folds: list[WalkForwardFold] = Field(min_length=2, max_length=1000)


class CausalPipelineSpecification(StrictModel):
    schema_version: Literal["causal-feature-label-split-v1.0.0"]
    decision_clock: Literal["decision_open", "decision_close"]
    features: list[FeatureBinding] = Field(min_length=1, max_length=1000)
    labels: list[LabelContract] = Field(min_length=1, max_length=100)
    fitted_transforms: list[FittedTransform] = Field(
        default_factory=list, max_length=100
    )
    split: SplitContract
    sample_weighting: Literal["uniform", "inverse_label_overlap"]
    action_authority: Literal[False] = False

    @model_validator(mode="after")
    def causal_boundaries(self):
        feature_keys = [item.feature_key for item in self.features]
        if len(feature_keys) != len(set(feature_keys)):
            raise ValueError("feature keys must be unique")
        label_keys = [item.label_key for item in self.labels]
        if len(label_keys) != len(set(label_keys)):
            raise ValueError("label keys must be unique")
        maximum_end = max(item.label_end_offset_bars for item in self.labels)
        if self.split.purge_bars < maximum_end:
            raise ValueError("purge_bars must cover the maximum label end offset")
        folds = self.split.folds
        if [item.fold for item in folds] != list(range(1, len(folds) + 1)):
            raise ValueError("fold numbers must be contiguous from one")
        for fold in folds:
            if fold.validation_start - fold.train_end < self.split.purge_bars:
                raise ValueError("every fold must preserve the declared purge boundary")
        for prior, current in pairwise(folds):
            if (
                current.train_start != folds[0].train_start
                or current.train_end <= prior.train_end
            ):
                raise ValueError("walk-forward training windows must expand")
            if (
                current.validation_start
                < prior.validation_end + self.split.embargo_bars
            ):
                raise ValueError("validation folds must preserve the declared embargo")
        return self


class CausalPipelineCreate(StrictModel):
    pipeline_key: str = Field(pattern=_KEY, max_length=180)
    dataset_build_id: UUID
    factor_program_id: UUID
    specification: CausalPipelineSpecification
    specification_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_KEY, max_length=150)


class CausalPipelineResponse(CausalPipelineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    compiled: dict
    compiled_digest: str
    registered_at: datetime


class FoldMaterializationResult(StrictModel):
    fold: int = Field(ge=1)
    train_rows: int = Field(ge=1)
    validation_rows: int = Field(ge=1)
    maximum_train_label_end: int = Field(ge=0)
    minimum_validation_feature_time: int = Field(ge=0)
    purge_passed: bool
    embargo_passed: bool
    train_only_fit_passed: bool
    point_in_time_join_passed: bool


class CausalMaterializationCreate(StrictModel):
    materialization_key: str = Field(pattern=_KEY, max_length=180)
    pipeline_id: UUID
    output_uri: str = Field(min_length=1, max_length=1000)
    row_count: int = Field(ge=1)
    fold_results: list[FoldMaterializationResult] = Field(min_length=2, max_length=1000)
    content_digest: str = Field(pattern=_DIGEST)
    rebuild_content_digest: str = Field(pattern=_DIGEST)
    record_digest: str = Field(pattern=_DIGEST)
    built_by: str = Field(pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def proof_is_consistent(self):
        if self.content_digest != self.rebuild_content_digest:
            raise ValueError(
                "independent materialization rebuild digest does not match"
            )
        checks = (
            "purge_passed",
            "embargo_passed",
            "train_only_fit_passed",
            "point_in_time_join_passed",
        )
        if any(
            not getattr(fold, check) for fold in self.fold_results for check in checks
        ):
            raise ValueError("every fold must pass all causal materialization checks")
        if (
            sum(item.train_rows + item.validation_rows for item in self.fold_results)
            < self.row_count
        ):
            raise ValueError("fold row evidence cannot be smaller than row_count")
        return self


class CausalMaterializationResponse(CausalMaterializationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    registered_at: datetime
