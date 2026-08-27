from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_SYMBOL = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
_DIGEST = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemporalRecord(StrictModel):
    valid_from: datetime
    valid_to: datetime | None = None
    observed_at: datetime
    available_at: datetime
    revision_id: str = Field(pattern=_KEY, max_length=150)
    corrects_revision_id: str | None = Field(default=None, pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def valid_temporal_record(self) -> TemporalRecord:
        values = (self.valid_from, self.valid_to, self.observed_at, self.available_at)
        if any(value is not None and value.utcoffset() is None for value in values):
            raise ValueError("reference timestamps must be timezone-aware")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        if self.corrects_revision_id == self.revision_id:
            raise ValueError("a revision cannot correct itself")
        return self


class VenueRecord(TemporalRecord):
    venue_id: str = Field(pattern=_KEY, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    mic: str | None = Field(default=None, pattern=r"^[A-Z0-9]{4}$")
    timezone: str = Field(min_length=1, max_length=100)
    calendar_id: str = Field(pattern=_KEY, max_length=100)


class InstrumentRecord(TemporalRecord):
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    asset_class: Literal[
        "crypto_spot",
        "crypto_perpetual",
        "crypto_future",
        "equity",
        "etf",
        "future",
        "option",
        "fx",
        "index",
    ]
    base_asset: str = Field(pattern=_KEY, max_length=100)
    quote_asset: str = Field(pattern=_KEY, max_length=100)
    settlement_asset: str = Field(pattern=_KEY, max_length=100)
    contract_type: Literal[
        "spot", "perpetual", "dated_future", "option", "cash_equity", "index"
    ]
    expiry_at: datetime | None = None


class ListingRecord(TemporalRecord):
    listing_id: str = Field(pattern=_KEY, max_length=150)
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    venue_id: str = Field(pattern=_KEY, max_length=100)
    symbol: str = Field(pattern=_SYMBOL, max_length=100)
    status: Literal["announced", "active", "suspended", "delisted"]
    price_increment: float = Field(gt=0)
    quantity_increment: float = Field(gt=0)
    contract_multiplier: float = Field(gt=0)


class DailySession(StrictModel):
    weekday: int = Field(ge=0, le=6)
    opens_at: time
    closes_at: time

class SessionCalendarRecord(TemporalRecord):
    calendar_id: str = Field(pattern=_KEY, max_length=100)
    timezone: str = Field(min_length=1, max_length=100)
    sessions: list[DailySession] = Field(min_length=1, max_length=14)
    holidays: list[date] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique_sessions_and_holidays(self) -> SessionCalendarRecord:
        keys = [(item.weekday, item.opens_at, item.closes_at) for item in self.sessions]
        if len(keys) != len(set(keys)):
            raise ValueError("calendar sessions must be unique")
        if len(self.holidays) != len(set(self.holidays)):
            raise ValueError("calendar holidays must be unique")
        return self


class CorporateActionRecord(StrictModel):
    action_id: str = Field(pattern=_KEY, max_length=150)
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    action_type: Literal[
        "symbol_change",
        "listing",
        "delisting",
        "split",
        "reverse_split",
        "dividend",
        "merger",
        "spinoff",
        "contract_specification_change",
    ]
    effective_at: datetime
    announced_at: datetime
    available_at: datetime
    terms: dict[str, str | int | float | bool] = Field(default_factory=dict)
    revision_id: str = Field(pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def known_after_announcement(self) -> CorporateActionRecord:
        if self.available_at < self.announced_at:
            raise ValueError("corporate action availability cannot precede announcement")
        return self


class PointInTimeReferenceSnapshot(StrictModel):
    schema_version: Literal[1]
    as_of: datetime
    source: str = Field(pattern=_KEY, max_length=150)
    source_revision: str = Field(pattern=_KEY, max_length=150)
    venues: list[VenueRecord] = Field(min_length=1, max_length=1000)
    instruments: list[InstrumentRecord] = Field(min_length=1, max_length=100_000)
    listings: list[ListingRecord] = Field(min_length=1, max_length=200_000)
    calendars: list[SessionCalendarRecord] = Field(min_length=1, max_length=1000)
    corporate_actions: list[CorporateActionRecord] = Field(
        default_factory=list, max_length=1_000_000
    )

    @model_validator(mode="after")
    def closed_reference_graph(self) -> PointInTimeReferenceSnapshot:
        if self.as_of.utcoffset() is None:
            raise ValueError("snapshot as_of must be timezone-aware")
        temporal = [*self.venues, *self.instruments, *self.listings, *self.calendars]
        if any(record.available_at > self.as_of for record in temporal):
            raise ValueError("record availability cannot exceed snapshot as_of")
        if any(action.available_at > self.as_of for action in self.corporate_actions):
            raise ValueError("corporate action availability cannot exceed snapshot as_of")
        revisions = [item.revision_id for item in temporal] + [
            item.revision_id for item in self.corporate_actions
        ]
        _require_unique(revisions, "record revisions")
        revision_ids = set(revisions)
        if any(
            item.corrects_revision_id not in revision_ids
            for item in temporal
            if item.corrects_revision_id is not None
        ):
            raise ValueError("corrected reference revision is absent from snapshot")
        _require_unique(
            [item.action_id for item in self.corporate_actions], "corporate actions"
        )
        venue_ids = {item.venue_id for item in self.venues}
        instrument_ids = {item.instrument_id for item in self.instruments}
        calendar_ids = {item.calendar_id for item in self.calendars}
        if any(item.calendar_id not in calendar_ids for item in self.venues):
            raise ValueError("venue references an unknown calendar")
        if any(item.venue_id not in venue_ids for item in self.listings):
            raise ValueError("listing references an unknown venue")
        if any(item.instrument_id not in instrument_ids for item in self.listings):
            raise ValueError("listing references an unknown instrument")
        if any(
            item.instrument_id not in instrument_ids for item in self.corporate_actions
        ):
            raise ValueError("corporate action references an unknown instrument")
        _reject_overlapping_versions(self.venues, "venue_id")
        _reject_overlapping_versions(self.instruments, "instrument_id")
        _reject_overlapping_versions(self.listings, "listing_id")
        _reject_overlapping_versions(self.calendars, "calendar_id")
        _reject_overlapping_symbols(self.listings)
        return self


class ReferenceSnapshotCreate(StrictModel):
    snapshot_key: str = Field(pattern=_KEY, max_length=150)
    snapshot: PointInTimeReferenceSnapshot
    snapshot_digest: str = Field(pattern=_DIGEST)
    supersedes_snapshot_id: uuid.UUID | None = None
    registered_by: str = Field(pattern=_KEY, max_length=150)


class ReferenceSnapshotResponse(ReferenceSnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    as_of: datetime
    registered_at: datetime


class ReferenceResolveRequest(StrictModel):
    venue_id: str = Field(pattern=_KEY, max_length=100)
    symbol: str = Field(pattern=_SYMBOL, max_length=100)
    effective_at: datetime
    known_at: datetime
    snapshot_digest: str | None = Field(default=None, pattern=_DIGEST)

    @model_validator(mode="after")
    def aware_clocks(self) -> ReferenceResolveRequest:
        if self.effective_at.utcoffset() is None or self.known_at.utcoffset() is None:
            raise ValueError("resolution clocks must be timezone-aware")
        return self


class ReferenceResolution(StrictModel):
    snapshot_id: uuid.UUID | None
    snapshot_digest: str
    snapshot_as_of: datetime
    known_at: datetime
    effective_at: datetime
    instrument: InstrumentRecord
    listing: ListingRecord
    venue: VenueRecord
    calendar: SessionCalendarRecord
    session_open: bool
    known_corporate_actions: list[CorporateActionRecord]
    claim_boundary: str


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique within a snapshot")


def _overlaps(first: TemporalRecord, second: TemporalRecord) -> bool:
    end_first = first.valid_to or datetime.max.replace(tzinfo=UTC)
    end_second = second.valid_to or datetime.max.replace(tzinfo=UTC)
    return first.valid_from < end_second and second.valid_from < end_first


def _reject_overlapping_symbols(listings: list[ListingRecord]) -> None:
    for index, first in enumerate(listings):
        for second in listings[index + 1 :]:
            if (
                first.venue_id == second.venue_id
                and first.symbol.casefold() == second.symbol.casefold()
                and _overlaps(first, second)
            ):
                raise ValueError("venue symbol identity is temporally ambiguous")


def _reject_overlapping_versions(records: list[TemporalRecord], key: str) -> None:
    for index, first in enumerate(records):
        for second in records[index + 1 :]:
            if getattr(first, key) == getattr(second, key) and _overlaps(first, second):
                raise ValueError(f"{key} revisions overlap")
