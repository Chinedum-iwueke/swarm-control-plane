from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_ACTOR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderIdentity(StrictModel):
    name: str = Field(pattern=_KEY, max_length=100)
    dataset: str = Field(pattern=_KEY, max_length=150)
    venue: str = Field(pattern=_KEY, max_length=100)
    asset_class: str = Field(pattern=_KEY, max_length=100)
    retrieval_method: Literal["api", "bulk_archive", "local_canonical_store"]
    terms_version: str = Field(min_length=1, max_length=150)


class SourceObject(StrictModel):
    uri: str = Field(min_length=1, max_length=1000)
    sha256: str = Field(pattern=_DIGEST)
    observed_at: datetime
    available_at: datetime
    revision_id: str = Field(pattern=_KEY, max_length=150)
    rows: int = Field(ge=1, le=1_000_000_000)


class CorporateActionPolicy(StrictModel):
    mode: Literal["not_applicable", "raw_with_events", "provider_adjusted"]
    events_digest: str | None = Field(default=None, pattern=_DIGEST)
    description: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def events_are_bound(self) -> CorporateActionPolicy:
        if self.mode == "raw_with_events" and self.events_digest is None:
            raise ValueError("raw_with_events requires events_digest")
        if self.mode != "raw_with_events" and self.events_digest is not None:
            raise ValueError("events_digest is only valid for raw_with_events")
        return self


class TransformationStep(StrictModel):
    order: int = Field(ge=1, le=1000)
    name: str = Field(pattern=_KEY, max_length=150)
    operation: str = Field(min_length=3, max_length=1000)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    input_columns: list[str] = Field(min_length=1, max_length=100)
    output_columns: list[str] = Field(min_length=1, max_length=100)


class FeatureDefinition(StrictModel):
    feature_key: str = Field(pattern=_KEY, max_length=150)
    expression: str = Field(min_length=3, max_length=1000)
    input_columns: list[str] = Field(min_length=1, max_length=100)
    lookback_bars: int = Field(ge=0, le=1_000_000)
    availability_lag_bars: int = Field(ge=0, le=1_000_000)
    null_policy: Literal["drop", "preserve", "constant"]
    null_constant: float | int | str | None = None

    @model_validator(mode="after")
    def constant_is_explicit(self) -> FeatureDefinition:
        if self.null_policy == "constant" and self.null_constant is None:
            raise ValueError("constant null policy requires null_constant")
        if self.null_policy != "constant" and self.null_constant is not None:
            raise ValueError("null_constant is only valid with constant policy")
        return self


class QualityAssertion(StrictModel):
    check: Literal[
        "duplicate_timestamp_count",
        "missing_bar_count",
        "non_finite_value_count",
        "non_positive_price_count",
        "out_of_order_timestamp_count",
    ]
    maximum: int = Field(ge=0)


class PointInTimeDatasetManifest(StrictModel):
    schema_version: Literal[1]
    provider: ProviderIdentity
    instruments: list[str] = Field(min_length=1, max_length=500)
    timeframe: str = Field(pattern=_KEY, max_length=50)
    date_start: datetime
    date_end: datetime
    as_of: datetime
    timezone: Literal["UTC"]
    source_objects: list[SourceObject] = Field(min_length=1, max_length=10_000)
    revision_policy: Literal["exact_revision", "latest_known_as_of"]
    fallback_policy: Literal["forbidden", "explicit_manifest_only"]
    fallback_provider: ProviderIdentity | None = None
    fallback_reason: str | None = Field(default=None, max_length=2000)
    corporate_actions: CorporateActionPolicy
    transformations: list[TransformationStep] = Field(min_length=1, max_length=1000)
    features: list[FeatureDefinition] = Field(min_length=1, max_length=1000)
    output_columns: list[str] = Field(min_length=1, max_length=500)
    quality_assertions: list[QualityAssertion] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def point_in_time_constraints(self) -> PointInTimeDatasetManifest:
        if self.date_end <= self.date_start:
            raise ValueError("date_end must be after date_start")
        if self.as_of < self.date_end:
            raise ValueError("as_of cannot precede date_end")
        if any(source.available_at > self.as_of for source in self.source_objects):
            raise ValueError("source availability cannot exceed as_of")
        if any(source.observed_at > self.as_of for source in self.source_objects):
            raise ValueError("source observation cannot exceed as_of")
        orders = [step.order for step in self.transformations]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("transformation order must be contiguous from one")
        feature_keys = [feature.feature_key for feature in self.features]
        if len(feature_keys) != len(set(feature_keys)):
            raise ValueError("feature keys must be unique")
        checks = [assertion.check for assertion in self.quality_assertions]
        if len(checks) != len(set(checks)):
            raise ValueError("quality checks must be unique")
        if self.fallback_policy == "forbidden" and (
            self.fallback_provider is not None or self.fallback_reason is not None
        ):
            raise ValueError("forbidden fallback cannot declare a provider")
        if self.fallback_policy == "explicit_manifest_only" and (
            self.fallback_provider is None or not self.fallback_reason
        ):
            raise ValueError("explicit fallback requires provider and reason")
        return self


class DatasetManifestCreate(StrictModel):
    manifest_key: str = Field(pattern=_KEY, max_length=150)
    manifest: PointInTimeDatasetManifest
    manifest_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class QualityResult(StrictModel):
    check: str = Field(pattern=_KEY, max_length=150)
    observed: int = Field(ge=0)
    maximum: int = Field(ge=0)
    passed: bool

    @model_validator(mode="after")
    def result_is_consistent(self) -> QualityResult:
        if self.passed != (self.observed <= self.maximum):
            raise ValueError("quality result does not match its threshold")
        return self


class DatasetBuildCreate(StrictModel):
    build_key: str = Field(pattern=_KEY, max_length=150)
    manifest_id: uuid.UUID
    builder_repository: str = Field(pattern=_KEY, max_length=150)
    builder_commit: str = Field(pattern=_COMMIT)
    builder_runtime: str = Field(min_length=3, max_length=300)
    output_uri: str = Field(min_length=1, max_length=1000)
    rows: int = Field(ge=1, le=1_000_000_000)
    started_at: datetime
    ended_at: datetime
    content_digest: str = Field(pattern=_DIGEST)
    rebuild_content_digest: str = Field(pattern=_DIGEST)
    quality_results: list[QualityResult] = Field(min_length=1, max_length=100)
    record_digest: str = Field(pattern=_DIGEST)
    built_by: str = Field(pattern=_ACTOR, max_length=150)

    @model_validator(mode="after")
    def build_is_reproducible(self) -> DatasetBuildCreate:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        if self.content_digest != self.rebuild_content_digest:
            raise ValueError("independent rebuild digest does not match")
        if any(not result.passed for result in self.quality_results):
            raise ValueError("all declared quality checks must pass")
        return self


class DatasetManifestResponse(DatasetManifestCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    registered_at: datetime


class DatasetBuildResponse(DatasetBuildCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    registered_at: datetime
