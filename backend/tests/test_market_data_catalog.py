from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.market_data_catalog import router
from app.schemas.market_data_catalog import (
    ImmutableMarketDataCatalog,
    MarketDataCatalogCreate,
    MarketDataResolveRequest,
)
from app.schemas.reference_data import (
    DailySession,
    InstrumentRecord,
    ListingRecord,
    PointInTimeReferenceSnapshot,
    SessionCalendarRecord,
    VenueRecord,
)
from app.services.market_data_catalog import (
    MarketDataConflict,
    MarketDataUnknown,
    register_catalog,
    resolve_market_data,
)
from app.services.research import record_digest
from pydantic import ValidationError

T0 = datetime(2025, 1, 1, tzinfo=UTC)
MID = datetime(2025, 1, 2, tzinfo=UTC)
END = datetime(2025, 1, 3, tzinfo=UTC)
AS_OF = datetime(2025, 1, 5, tzinfo=UTC)
REFERENCE_DIGEST = "a" * 64


def reference() -> PointInTimeReferenceSnapshot:
    def temporal(revision_id: str):
        return {
            "valid_from": T0 - timedelta(days=1),
            "observed_at": T0 - timedelta(days=2),
            "available_at": T0 - timedelta(days=2),
            "revision_id": revision_id,
        }

    return PointInTimeReferenceSnapshot(
        schema_version=1,
        as_of=T0 - timedelta(days=1),
        source="data002-fixture",
        source_revision="r1",
        venues=[
            VenueRecord(
                venue_id="binance",
                name="Binance",
                timezone="UTC",
                calendar_id="crypto-utc",
                **temporal("venue-r1"),
            )
        ],
        instruments=[
            InstrumentRecord(
                instrument_id="crypto:btc-usdt-perpetual",
                asset_class="crypto_perpetual",
                base_asset="BTC",
                quote_asset="USDT",
                settlement_asset="USDT",
                contract_type="perpetual",
                **temporal("instrument-r1"),
            )
        ],
        listings=[
            ListingRecord(
                listing_id="binance:btc-perpetual",
                instrument_id="crypto:btc-usdt-perpetual",
                venue_id="binance",
                symbol="BTCUSDT",
                status="active",
                price_increment=0.1,
                quantity_increment=0.001,
                contract_multiplier=1,
                **temporal("listing-r1"),
            )
        ],
        calendars=[
            SessionCalendarRecord(
                calendar_id="crypto-utc",
                timezone="UTC",
                sessions=[
                    DailySession(weekday=day, opens_at=time(0), closes_at=time(0))
                    for day in range(7)
                ],
                holidays=[date(2025, 1, 20)],
                **temporal("calendar-r1"),
            )
        ],
        corporate_actions=[],
    )


def catalog(**updates) -> ImmutableMarketDataCatalog:
    document = {
        "schema_version": 1,
        "as_of": AS_OF,
        "reference_snapshot_digest": REFERENCE_DIGEST,
        "partitions": [
            {
                "partition_id": "btc-1h-r1",
                "partition_key": "btc-1h-20250101",
                "dataset_key": "binance-perpetual-klines",
                "layer": "raw",
                "source_key": "binance-archive",
                "venue_id": "binance",
                "instrument_id": "crypto:btc-usdt-perpetual",
                "listing_id": "binance:btc-perpetual",
                "timeframe": "1h",
                "uri": "bulletproof://raw/binance/BTCUSDT/2025-01-01.parquet",
                "access_mode": "read_only",
                "content_digest": "b" * 64,
                "schema_digest": "c" * 64,
                "rows": 48,
                "duplicate_count": 0,
                "gap_count": 0,
                "event_start": T0,
                "event_end": END,
                "observed_at": END,
                "available_at": END + timedelta(minutes=5),
                "revision_id": "partition-r1",
            },
            {
                "partition_id": "btc-1h-r2",
                "partition_key": "btc-1h-20250101",
                "dataset_key": "binance-perpetual-klines",
                "layer": "raw",
                "source_key": "binance-archive",
                "venue_id": "binance",
                "instrument_id": "crypto:btc-usdt-perpetual",
                "listing_id": "binance:btc-perpetual",
                "timeframe": "1h",
                "uri": "bulletproof://raw/binance/BTCUSDT/2025-01-01-r2.parquet",
                "access_mode": "read_only",
                "content_digest": "d" * 64,
                "schema_digest": "c" * 64,
                "rows": 48,
                "duplicate_count": 0,
                "gap_count": 0,
                "event_start": T0,
                "event_end": END,
                "observed_at": END + timedelta(days=1),
                "available_at": END + timedelta(days=1, minutes=5),
                "revision_id": "partition-r2",
                "corrects_revision_id": "partition-r1",
            },
        ],
        "memberships": [
            {
                "membership_id": "liquid-btc-r1",
                "universe_key": "liquid-perpetuals",
                "instrument_id": "crypto:btc-usdt-perpetual",
                "effective_from": T0,
                "effective_to": END,
                "observed_at": T0,
                "available_at": T0,
                "revision_id": "membership-r1",
            }
        ],
        "source_availability": [
            {
                "availability_id": "binance-archive-r1",
                "source_key": "binance-archive",
                "status": "available",
                "coverage_start": T0,
                "coverage_end": END,
                "observed_at": END,
                "available_at": END + timedelta(minutes=1),
                "revision_id": "availability-r1",
            }
        ],
    }
    document.update(updates)
    return ImmutableMarketDataCatalog.model_validate(document)


def request(*, known_at: datetime = AS_OF, effective_at: datetime = MID):
    return MarketDataResolveRequest(
        dataset_key="binance-perpetual-klines",
        layer="raw",
        venue_id="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        effective_at=effective_at,
        known_at=known_at,
        universe_key="liquid-perpetuals",
    )


def db_for(value: ImmutableMarketDataCatalog):
    catalog_record = SimpleNamespace(
        id=uuid4(),
        catalog=value.model_dump(mode="json"),
        catalog_digest=record_digest(value),
        as_of=value.as_of,
        reference_snapshot_digest=REFERENCE_DIGEST,
    )
    reference_value = reference()
    reference_record = SimpleNamespace(
        id=uuid4(),
        snapshot=reference_value.model_dump(mode="json"),
        snapshot_digest=REFERENCE_DIGEST,
        as_of=reference_value.as_of,
    )
    db = MagicMock()
    db.scalar.side_effect = [catalog_record, reference_record]
    return db


def test_latest_known_correction_is_selected_without_lookahead() -> None:
    value = catalog()
    before = resolve_market_data(
        db_for(value), request(known_at=END + timedelta(minutes=30))
    )
    after = resolve_market_data(db_for(value), request())
    assert before.partition.revision_id == "partition-r1"
    assert after.partition.revision_id == "partition-r2"
    assert before.instrument_id == after.instrument_id


def test_gap_and_membership_drift_fail_closed() -> None:
    value = catalog()
    with pytest.raises(MarketDataUnknown, match="partition"):
        resolve_market_data(
            db_for(value), request(effective_at=END + timedelta(hours=1))
        )
    expired = value.memberships[0].model_copy(update={"effective_to": MID})
    changed = value.model_copy(update={"memberships": [expired]})
    with pytest.raises(MarketDataUnknown, match="membership"):
        resolve_market_data(db_for(changed), request())


def test_delayed_source_fails_closed() -> None:
    value = catalog()
    delayed = value.source_availability[0].model_copy(
        update={"status": "delayed", "reason": "archive publication delayed"}
    )
    changed = value.model_copy(update={"source_availability": [delayed]})
    with pytest.raises(MarketDataUnknown, match="delayed"):
        resolve_market_data(db_for(changed), request())


def test_duplicates_ambiguous_partitions_and_timezone_naive_clocks_are_rejected() -> (
    None
):
    value = catalog()
    duplicate = value.partitions[0].model_copy(update={"partition_id": "btc-copy"})
    with pytest.raises(ValidationError, match="revisions must be unique"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(
                update={"partitions": [*value.partitions, duplicate]}
            ).model_dump()
        )
    ambiguous = value.partitions[0].model_copy(
        update={
            "partition_id": "btc-other",
            "partition_key": "btc-other-key",
            "revision_id": "partition-other-r1",
        }
    )
    with pytest.raises(ValidationError, match="ambiguous"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(
                update={"partitions": [*value.partitions, ambiguous]}
            ).model_dump()
        )
    document = value.model_dump()
    document["partitions"][0]["event_start"] = T0.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone aware"):
        ImmutableMarketDataCatalog.model_validate(document)


def test_partition_duplicate_and_gap_counts_fail_laboratory_admission() -> None:
    value = catalog()
    duplicate = value.partitions[1].model_copy(update={"duplicate_count": 1})
    changed = value.model_copy(update={"partitions": [value.partitions[0], duplicate]})
    with pytest.raises(MarketDataUnknown, match="duplicate"):
        resolve_market_data(db_for(changed), request())


def test_correction_cannot_switch_logical_identity() -> None:
    value = catalog()
    changed_identity = value.partitions[1].model_copy(
        update={"listing_id": "binance:other-listing"}
    )
    with pytest.raises(ValidationError, match="logical record identity"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(
                update={"partitions": [value.partitions[0], changed_identity]}
            ).model_dump()
        )


def test_late_correction_requires_ancestry_and_order() -> None:
    value = catalog()
    broken = value.partitions[1].model_copy(update={"corrects_revision_id": "missing"})
    with pytest.raises(ValidationError, match="ancestry"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(
                update={"partitions": [value.partitions[0], broken]}
            ).model_dump()
        )
    early = value.partitions[1].model_copy(
        update={
            "observed_at": value.partitions[0].observed_at,
            "available_at": value.partitions[0].available_at,
        }
    )
    with pytest.raises(ValidationError, match="after its ancestor"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(
                update={"partitions": [value.partitions[0], early]}
            ).model_dump()
        )


def test_catalog_registration_binds_digest_reference_and_supersession() -> None:
    value = catalog()
    payload = MarketDataCatalogCreate(
        catalog_key="DATA002-BTC-R1",
        catalog=value,
        catalog_digest=record_digest(value),
        registered_by="data002-pilot",
    )
    db = MagicMock()
    reference_value = reference()
    reference_record = SimpleNamespace(snapshot=reference_value.model_dump(mode="json"))
    db.scalar.side_effect = [reference_record, None]
    record = register_catalog(db, payload)
    assert record.catalog_digest == payload.catalog_digest
    assert record.reference_snapshot_digest == REFERENCE_DIGEST
    with pytest.raises(MarketDataConflict, match="digest"):
        register_catalog(db, payload.model_copy(update={"catalog_digest": "f" * 64}))


def test_registration_rejects_identity_absent_from_reference_snapshot() -> None:
    value = catalog()
    bad = [item.model_copy(update={"venue_id": "bybit"}) for item in value.partitions]
    changed = value.model_copy(update={"partitions": bad})
    payload = MarketDataCatalogCreate(
        catalog_key="DATA002-BAD-IDENTITY",
        catalog=changed,
        catalog_digest=record_digest(changed),
        registered_by="data002-pilot",
    )
    reference_value = reference()
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        snapshot=reference_value.model_dump(mode="json")
    )
    with pytest.raises(MarketDataConflict, match="venue"):
        register_catalog(db, payload)


def test_source_must_be_read_only_and_have_availability_ledger() -> None:
    value = catalog()
    document = value.model_dump()
    document["partitions"][0]["access_mode"] = "write"
    with pytest.raises(ValidationError):
        ImmutableMarketDataCatalog.model_validate(document)
    with pytest.raises(ValidationError, match="at least 1"):
        ImmutableMarketDataCatalog.model_validate(
            value.model_copy(update={"source_availability": []}).model_dump()
        )


def test_market_data_catalog_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/v1/research/market-data-catalog/snapshots" in paths
    assert "/v1/research/market-data-catalog/resolve" in paths
