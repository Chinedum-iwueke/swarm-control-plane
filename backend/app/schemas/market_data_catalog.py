from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_DIGEST = r"^[0-9a-f]{64}$"
_ACTOR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogPartition(StrictModel):
    partition_id: str = Field(pattern=_KEY, max_length=200)
    partition_key: str = Field(pattern=_KEY, max_length=200)
    dataset_key: str = Field(pattern=_KEY, max_length=150)
    layer: Literal["raw", "curated"]
    source_key: str = Field(pattern=_KEY, max_length=150)
    venue_id: str = Field(pattern=_KEY, max_length=100)
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    listing_id: str = Field(pattern=_KEY, max_length=150)
    timeframe: str = Field(pattern=_KEY, max_length=50)
    uri: str = Field(min_length=1, max_length=1000)
    access_mode: Literal["read_only"]
    content_digest: str = Field(pattern=_DIGEST)
    schema_digest: str = Field(pattern=_DIGEST)
    rows: int = Field(ge=1, le=1_000_000_000)
    duplicate_count: int = Field(ge=0, le=1_000_000_000)
    gap_count: int = Field(ge=0, le=1_000_000_000)
    event_start: datetime
    event_end: datetime
    observed_at: datetime
    available_at: datetime
    revision_id: str = Field(pattern=_KEY, max_length=150)
    corrects_revision_id: str | None = Field(default=None, pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def clocks_are_ordered(self) -> CatalogPartition:
        _aware(self.event_start, self.event_end, self.observed_at, self.available_at)
        if self.event_end <= self.event_start:
            raise ValueError("partition event_end must be after event_start")
        if self.available_at < self.observed_at:
            raise ValueError("partition availability cannot precede observation")
        return self


class CatalogMembership(StrictModel):
    membership_id: str = Field(pattern=_KEY, max_length=200)
    universe_key: str = Field(pattern=_KEY, max_length=150)
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    effective_from: datetime
    effective_to: datetime | None = None
    observed_at: datetime
    available_at: datetime
    revision_id: str = Field(pattern=_KEY, max_length=150)
    corrects_revision_id: str | None = Field(default=None, pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def clocks_are_ordered(self) -> CatalogMembership:
        values = [self.effective_from, self.observed_at, self.available_at]
        if self.effective_to is not None:
            values.append(self.effective_to)
        _aware(*values)
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("membership effective_to must follow effective_from")
        if self.available_at < self.observed_at:
            raise ValueError("membership availability cannot precede observation")
        return self


class SourceAvailability(StrictModel):
    availability_id: str = Field(pattern=_KEY, max_length=200)
    source_key: str = Field(pattern=_KEY, max_length=150)
    status: Literal["available", "delayed", "unavailable"]
    coverage_start: datetime
    coverage_end: datetime
    observed_at: datetime
    available_at: datetime
    revision_id: str = Field(pattern=_KEY, max_length=150)
    corrects_revision_id: str | None = Field(default=None, pattern=_KEY, max_length=150)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def clocks_are_ordered(self) -> SourceAvailability:
        _aware(
            self.coverage_start,
            self.coverage_end,
            self.observed_at,
            self.available_at,
        )
        if self.coverage_end <= self.coverage_start:
            raise ValueError("availability coverage_end must follow coverage_start")
        if self.available_at < self.observed_at:
            raise ValueError("source availability cannot precede observation")
        if self.status != "available" and not self.reason:
            raise ValueError("non-available source status requires a reason")
        return self


class ImmutableMarketDataCatalog(StrictModel):
    schema_version: Literal[1]
    as_of: datetime
    reference_snapshot_digest: str = Field(pattern=_DIGEST)
    partitions: list[CatalogPartition] = Field(min_length=1, max_length=50_000)
    memberships: list[CatalogMembership] = Field(
        default_factory=list, max_length=50_000
    )
    source_availability: list[SourceAvailability] = Field(
        min_length=1, max_length=50_000
    )

    @model_validator(mode="after")
    def catalog_is_temporally_closed(self) -> ImmutableMarketDataCatalog:
        _aware(self.as_of)
        all_items = [*self.partitions, *self.memberships, *self.source_availability]
        if any(item.available_at > self.as_of for item in all_items):
            raise ValueError("catalog cannot contain information unavailable at as_of")
        _unique([item.partition_id for item in self.partitions], "partition IDs")
        _unique([item.revision_id for item in self.partitions], "partition revisions")
        _unique([item.membership_id for item in self.memberships], "membership IDs")
        _unique([item.revision_id for item in self.memberships], "membership revisions")
        _unique(
            [item.availability_id for item in self.source_availability],
            "availability IDs",
        )
        _unique(
            [item.revision_id for item in self.source_availability],
            "availability revisions",
        )
        _validate_corrections(self.partitions)
        _validate_corrections(self.memberships)
        _validate_corrections(self.source_availability)
        _validate_partition_ambiguity(self.partitions)
        known_sources = {item.source_key for item in self.source_availability}
        if any(item.source_key not in known_sources for item in self.partitions):
            raise ValueError("every partition source requires an availability ledger")
        return self


class MarketDataCatalogCreate(StrictModel):
    catalog_key: str = Field(pattern=_KEY, max_length=150)
    catalog: ImmutableMarketDataCatalog
    catalog_digest: str = Field(pattern=_DIGEST)
    supersedes_catalog_id: uuid.UUID | None = None
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class MarketDataCatalogResponse(MarketDataCatalogCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reference_snapshot_digest: str
    as_of: datetime
    registered_at: datetime


class MarketDataResolveRequest(StrictModel):
    dataset_key: str = Field(pattern=_KEY, max_length=150)
    layer: Literal["raw", "curated"]
    venue_id: str = Field(pattern=_KEY, max_length=100)
    symbol: str = Field(min_length=1, max_length=100)
    timeframe: str = Field(pattern=_KEY, max_length=50)
    effective_at: datetime
    known_at: datetime
    universe_key: str | None = Field(default=None, pattern=_KEY, max_length=150)
    catalog_digest: str | None = Field(default=None, pattern=_DIGEST)

    @model_validator(mode="after")
    def request_clocks_are_aware(self) -> MarketDataResolveRequest:
        _aware(self.effective_at, self.known_at)
        return self


class MarketDataResolution(StrictModel):
    catalog_id: uuid.UUID
    catalog_digest: str
    catalog_as_of: datetime
    reference_snapshot_digest: str
    effective_at: datetime
    known_at: datetime
    instrument_id: str
    listing_id: str
    partition: CatalogPartition
    membership: CatalogMembership | None
    source_availability: SourceAvailability
    claim_boundary: str


def _aware(*values: datetime) -> None:
    if any(value.tzinfo is None or value.utcoffset() is None for value in values):
        raise ValueError("all catalog clocks must be timezone aware")


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_corrections(items: list) -> None:
    revisions = {item.revision_id: item for item in items}
    for item in items:
        if item.corrects_revision_id is None:
            continue
        prior = revisions.get(item.corrects_revision_id)
        if prior is None:
            raise ValueError("correction ancestry must exist in the catalog")
        if item.available_at <= prior.available_at:
            raise ValueError("a correction must become available after its ancestor")
        if _correction_identity(item) != _correction_identity(prior):
            raise ValueError("a correction cannot change logical record identity")


def _correction_identity(item) -> tuple:
    if isinstance(item, CatalogPartition):
        return (
            item.partition_key,
            item.dataset_key,
            item.layer,
            item.source_key,
            item.venue_id,
            item.instrument_id,
            item.listing_id,
            item.timeframe,
            item.event_start,
            item.event_end,
        )
    if isinstance(item, CatalogMembership):
        return item.universe_key, item.instrument_id
    return item.source_key, item.coverage_start, item.coverage_end


def _validate_partition_ambiguity(items: list[CatalogPartition]) -> None:
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            identity = (
                left.dataset_key,
                left.layer,
                left.instrument_id,
                left.timeframe,
            )
            other = (
                right.dataset_key,
                right.layer,
                right.instrument_id,
                right.timeframe,
            )
            overlaps = (
                left.event_start < right.event_end
                and right.event_start < left.event_end
            )
            if (
                identity == other
                and overlaps
                and left.partition_key != right.partition_key
            ):
                raise ValueError("overlapping logical partitions make replay ambiguous")
