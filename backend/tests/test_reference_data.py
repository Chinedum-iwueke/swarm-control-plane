from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.reference_data import router
from app.schemas.reference_data import (
    CorporateActionRecord,
    DailySession,
    InstrumentRecord,
    ListingRecord,
    PointInTimeReferenceSnapshot,
    ReferenceResolveRequest,
    ReferenceSnapshotCreate,
    SessionCalendarRecord,
    VenueRecord,
)
from app.services.reference_data import (
    ReferenceDataConflict,
    ReferenceDataUnknown,
    register_reference_snapshot,
    resolve_snapshot,
)
from app.services.research import record_digest
from pydantic import ValidationError

T0 = datetime(2024, 1, 1, tzinfo=UTC)
CHANGE = datetime(2025, 1, 1, tzinfo=UTC)
AS_OF = datetime(2025, 2, 1, tzinfo=UTC)


def temporal(revision: str, start: datetime = T0, end: datetime | None = None):
    return {
        "valid_from": start,
        "valid_to": end,
        "observed_at": start - timedelta(days=1),
        "available_at": start - timedelta(days=1),
        "revision_id": revision,
    }


def snapshot(*, as_of: datetime = AS_OF) -> PointInTimeReferenceSnapshot:
    calendar = SessionCalendarRecord(
        calendar_id="crypto-utc",
        timezone="UTC",
        sessions=[
            DailySession(weekday=weekday, opens_at=time(0), closes_at=time(0))
            for weekday in range(7)
        ],
        holidays=[date(2025, 1, 20)],
        **temporal("calendar-r1"),
    )
    venue = VenueRecord(
        venue_id="binance",
        name="Binance",
        timezone="UTC",
        calendar_id=calendar.calendar_id,
        **temporal("venue-r1"),
    )
    old_instrument = InstrumentRecord(
        instrument_id="crypto:btc-usdt-perpetual",
        asset_class="crypto_perpetual",
        base_asset="BTC",
        quote_asset="USDT",
        settlement_asset="USDT",
        contract_type="perpetual",
        **temporal("instrument-r1", end=CHANGE),
    )
    current_instrument = old_instrument.model_copy(
        update={
            "valid_from": CHANGE,
            "valid_to": None,
            "observed_at": CHANGE - timedelta(days=7),
            "available_at": CHANGE - timedelta(days=7),
            "revision_id": "instrument-r2",
            "corrects_revision_id": "instrument-r1",
        }
    )
    old_listing = ListingRecord(
        listing_id="binance:btc-perpetual",
        instrument_id=old_instrument.instrument_id,
        venue_id=venue.venue_id,
        symbol="BTCUSDT",
        status="active",
        price_increment=0.1,
        quantity_increment=0.001,
        contract_multiplier=1,
        **temporal("listing-r1", end=CHANGE),
    )
    current_listing = old_listing.model_copy(
        update={
            "symbol": "BTCUSDT-PERP",
            "valid_from": CHANGE,
            "valid_to": None,
            "observed_at": CHANGE - timedelta(days=7),
            "available_at": CHANGE - timedelta(days=7),
            "revision_id": "listing-r2",
            "corrects_revision_id": "listing-r1",
        }
    )
    action = CorporateActionRecord(
        action_id="binance:btc-symbol-change-2025",
        instrument_id=old_instrument.instrument_id,
        action_type="symbol_change",
        effective_at=CHANGE,
        announced_at=CHANGE - timedelta(days=7),
        available_at=CHANGE - timedelta(days=7),
        terms={"old_symbol": "BTCUSDT", "new_symbol": "BTCUSDT-PERP"},
        revision_id="action-r1",
    )
    return PointInTimeReferenceSnapshot(
        schema_version=1,
        as_of=as_of,
        source="data001-fixture",
        source_revision="fixture-r1",
        venues=[venue],
        instruments=[old_instrument, current_instrument],
        listings=[old_listing, current_listing],
        calendars=[calendar],
        corporate_actions=[action],
    )


def request(symbol: str, effective_at: datetime, known_at: datetime = AS_OF):
    return ReferenceResolveRequest(
        venue_id="binance",
        symbol=symbol,
        effective_at=effective_at,
        known_at=known_at,
    )


def test_symbol_change_replays_stable_identity_without_present_day_leakage() -> None:
    value = snapshot()
    prior = resolve_snapshot(value, request("BTCUSDT", CHANGE - timedelta(days=1)))
    current = resolve_snapshot(
        value, request("BTCUSDT-PERP", CHANGE + timedelta(days=1))
    )

    assert prior.instrument.instrument_id == current.instrument.instrument_id
    assert prior.listing.revision_id == "listing-r1"
    assert current.listing.revision_id == "listing-r2"
    with pytest.raises(ReferenceDataUnknown, match="unknown"):
        resolve_snapshot(value, request("BTCUSDT-PERP", CHANGE - timedelta(days=1)))


def test_nonoverlapping_relisting_is_historically_replayable() -> None:
    value = snapshot()
    relisted = value.listings[1].model_copy(
        update={
            "listing_id": "binance:btc-perpetual-relisting",
            "symbol": "BTCUSDT",
            "valid_from": CHANGE + timedelta(days=10),
            "observed_at": CHANGE + timedelta(days=9),
            "available_at": CHANGE + timedelta(days=9),
            "revision_id": "listing-relisted-r1",
            "corrects_revision_id": None,
        }
    )
    replayable = PointInTimeReferenceSnapshot.model_validate(
        value.model_copy(update={"listings": [*value.listings, relisted]}).model_dump()
    )

    before = resolve_snapshot(
        replayable, request("BTCUSDT", CHANGE - timedelta(days=1))
    )
    after = resolve_snapshot(
        replayable, request("BTCUSDT", CHANGE + timedelta(days=11))
    )
    assert before.listing.listing_id == "binance:btc-perpetual"
    assert after.listing.listing_id == "binance:btc-perpetual-relisting"


def test_known_at_filters_actions_and_future_snapshot() -> None:
    value = snapshot()
    before_announcement = CHANGE - timedelta(days=8)
    with pytest.raises(ReferenceDataUnknown, match="not yet available"):
        resolve_snapshot(value, request("BTCUSDT", T0, before_announcement))

    earlier = value.model_copy(update={"as_of": before_announcement})
    with pytest.raises(ValidationError, match="availability cannot exceed"):
        PointInTimeReferenceSnapshot.model_validate(earlier.model_dump())


def test_holiday_and_24_hour_session_replay() -> None:
    value = snapshot()
    holiday = resolve_snapshot(
        value, request("BTCUSDT-PERP", datetime(2025, 1, 20, 12, tzinfo=UTC))
    )
    ordinary = resolve_snapshot(
        value, request("BTCUSDT-PERP", datetime(2025, 1, 21, 12, tzinfo=UTC))
    )
    assert holiday.session_open is False
    assert ordinary.session_open is True


def test_symbol_reuse_overlap_and_clock_skew_fail_closed() -> None:
    value = snapshot()
    reused = value.listings[1].model_copy(
        update={
            "listing_id": "binance:other-contract",
            "instrument_id": value.instruments[0].instrument_id,
            "symbol": "BTCUSDT",
            "revision_id": "listing-other-r1",
            "valid_from": CHANGE - timedelta(days=1),
        }
    )
    with pytest.raises(ValidationError, match="temporally ambiguous"):
        PointInTimeReferenceSnapshot.model_validate(
            value.model_copy(update={"listings": [*value.listings, reused]}).model_dump()
        )
    with pytest.raises(ValidationError, match="cannot precede observed"):
        VenueRecord.model_validate(
            value.venues[0]
            .model_copy(update={"available_at": T0 - timedelta(days=2)})
            .model_dump()
        )


def test_unknown_venue_and_delisted_identity_are_explicit() -> None:
    value = snapshot()
    unknown = request("BTCUSDT-PERP", CHANGE + timedelta(days=1)).model_copy(
        update={"venue_id": "bybit"}
    )
    with pytest.raises(ReferenceDataUnknown):
        resolve_snapshot(value, unknown)
    delisted = value.listings[1].model_copy(update={"status": "delisted"})
    changed = value.model_copy(update={"listings": [value.listings[0], delisted]})
    result = resolve_snapshot(
        changed, request("BTCUSDT-PERP", CHANGE + timedelta(days=1))
    )
    assert result.listing.status == "delisted"


def test_registration_is_digest_bound_idempotent_and_supersession_is_ordered() -> None:
    value = snapshot()
    payload = ReferenceSnapshotCreate(
        snapshot_key="DATA001-FIXTURE-R1",
        snapshot=value,
        snapshot_digest=record_digest(value),
        registered_by="data001-pilot",
    )
    db = MagicMock()
    db.scalar.return_value = None
    record = register_reference_snapshot(db, payload)
    assert record.snapshot_digest == payload.snapshot_digest
    db.add.assert_called_once_with(record)

    with pytest.raises(ReferenceDataConflict, match="digest"):
        register_reference_snapshot(
            db,
            payload.model_copy(update={"snapshot_digest": "f" * 64}),
        )

    prior = MagicMock(id=uuid4(), as_of=AS_OF)
    db.scalar.return_value = None
    db.get.return_value = prior
    with pytest.raises(ReferenceDataConflict, match="later knowledge clock"):
        register_reference_snapshot(
            db,
            payload.model_copy(update={"supersedes_snapshot_id": prior.id}),
        )


def test_reference_data_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/v1/research/reference-data/snapshots" in paths
    assert "/v1/research/reference-data/resolve" in paths
