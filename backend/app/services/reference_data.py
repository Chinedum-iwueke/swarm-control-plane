from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference_data import ReferenceDataSnapshot
from app.schemas.reference_data import (
    PointInTimeReferenceSnapshot,
    ReferenceResolution,
    ReferenceResolveRequest,
    ReferenceSnapshotCreate,
)
from app.services.research import record_digest


class ReferenceDataConflict(ValueError):
    pass


class ReferenceDataUnknown(LookupError):
    pass


def register_reference_snapshot(
    db: Session, payload: ReferenceSnapshotCreate
) -> ReferenceDataSnapshot:
    digest = record_digest(payload.snapshot)
    if digest != payload.snapshot_digest:
        raise ReferenceDataConflict("Reference snapshot digest does not match payload.")
    existing = db.scalar(
        select(ReferenceDataSnapshot).where(
            ReferenceDataSnapshot.snapshot_key == payload.snapshot_key
        )
    )
    if existing is not None:
        if existing.snapshot_digest == payload.snapshot_digest:
            return existing
        raise ReferenceDataConflict("Reference snapshot key is already registered.")
    if payload.supersedes_snapshot_id is not None:
        prior = db.get(ReferenceDataSnapshot, payload.supersedes_snapshot_id)
        if prior is None:
            raise ReferenceDataUnknown("Superseded reference snapshot was not found.")
        if payload.snapshot.as_of <= prior.as_of:
            raise ReferenceDataConflict(
                "A superseding snapshot must have a later knowledge clock."
            )
    record = ReferenceDataSnapshot(
        snapshot_key=payload.snapshot_key,
        as_of=payload.snapshot.as_of,
        snapshot=payload.snapshot.model_dump(mode="json"),
        snapshot_digest=payload.snapshot_digest,
        supersedes_snapshot_id=payload.supersedes_snapshot_id,
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    return record


def resolve_registered_reference(
    db: Session, request: ReferenceResolveRequest
) -> ReferenceResolution:
    statement = select(ReferenceDataSnapshot).where(
        ReferenceDataSnapshot.as_of <= request.known_at
    )
    if request.snapshot_digest:
        statement = statement.where(
            ReferenceDataSnapshot.snapshot_digest == request.snapshot_digest
        )
    statement = statement.order_by(ReferenceDataSnapshot.as_of.desc()).limit(2)
    records = list(db.scalars(statement).all())
    if not records:
        raise ReferenceDataUnknown("No reference snapshot was known at that time.")
    record = records[0]
    snapshot = PointInTimeReferenceSnapshot.model_validate(record.snapshot)
    return resolve_snapshot(
        snapshot,
        request,
        snapshot_id=record.id,
        snapshot_digest=record.snapshot_digest,
    )


def resolve_snapshot(
    snapshot: PointInTimeReferenceSnapshot,
    request: ReferenceResolveRequest,
    *,
    snapshot_id=None,
    snapshot_digest: str | None = None,
) -> ReferenceResolution:
    if snapshot.as_of > request.known_at:
        raise ReferenceDataUnknown("Snapshot contains information not yet available.")
    listings = [
        item
        for item in snapshot.listings
        if item.venue_id == request.venue_id
        and item.symbol.casefold() == request.symbol.casefold()
        and _effective(item.valid_from, item.valid_to, request.effective_at)
        and item.available_at <= request.known_at
    ]
    if not listings:
        raise ReferenceDataUnknown("Instrument identity is unknown at the requested clocks.")
    if len(listings) != 1:
        raise ReferenceDataConflict("Instrument identity is ambiguous at the requested clocks.")
    listing = listings[0]
    instruments = [
        item
        for item in snapshot.instruments
        if item.instrument_id == listing.instrument_id
        and _effective(item.valid_from, item.valid_to, request.effective_at)
        and item.available_at <= request.known_at
    ]
    venues = [
        item
        for item in snapshot.venues
        if item.venue_id == listing.venue_id
        and _effective(item.valid_from, item.valid_to, request.effective_at)
        and item.available_at <= request.known_at
    ]
    if len(instruments) != 1 or len(venues) != 1:
        raise ReferenceDataConflict("Reference graph does not resolve uniquely.")
    venue = venues[0]
    calendars = [
        item
        for item in snapshot.calendars
        if item.calendar_id == venue.calendar_id
        and _effective(item.valid_from, item.valid_to, request.effective_at)
        and item.available_at <= request.known_at
    ]
    if len(calendars) != 1:
        raise ReferenceDataConflict("Session calendar does not resolve uniquely.")
    calendar = calendars[0]
    actions = sorted(
        (
            item
            for item in snapshot.corporate_actions
            if item.instrument_id == listing.instrument_id
            and item.available_at <= request.known_at
        ),
        key=lambda item: (item.effective_at, item.action_id),
    )
    digest = snapshot_digest or record_digest(snapshot)
    return ReferenceResolution(
        snapshot_id=snapshot_id,
        snapshot_digest=digest,
        snapshot_as_of=snapshot.as_of,
        known_at=request.known_at,
        effective_at=request.effective_at,
        instrument=instruments[0],
        listing=listing,
        venue=venue,
        calendar=calendar,
        session_open=_session_open(calendar, request.effective_at),
        known_corporate_actions=actions,
        claim_boundary=(
            "Exact immutable snapshot and dual-clock resolution; symbol similarity, "
            "present-day identity and unavailable revisions are never inferred."
        ),
    )


def _effective(start: datetime, end: datetime | None, at: datetime) -> bool:
    return start <= at and (end is None or at < end)


def _session_open(calendar, at: datetime) -> bool:
    try:
        local = at.astimezone(ZoneInfo(calendar.timezone))
    except ZoneInfoNotFoundError as exc:
        raise ReferenceDataConflict("Session calendar timezone is invalid.") from exc
    if local.date() in calendar.holidays:
        return False
    current = local.timetz().replace(tzinfo=None)
    for session in calendar.sessions:
        if session.weekday != local.weekday():
            continue
        if session.opens_at == session.closes_at:
            return True
        if session.opens_at < session.closes_at:
            if session.opens_at <= current < session.closes_at:
                return True
        elif current >= session.opens_at or current < session.closes_at:
            return True
    return False
