from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.alpha_data_admission import register_selected_panel_receipt

DIGEST = "a" * 64
COMMIT = "b" * 40


def receipt() -> dict:
    result = {
        "schema_version": "alpha001-real-data-admission-v2.0.0",
        "evidence_class": "live_exchange_history",
        "admitted": True,
        "venue": "bybit",
        "instrument": "BTCUSDT",
        "canonical_symbols": ["BTC-USDT-PERP"],
        "market": "perp",
        "timeframe": "1m",
        "row_count": 525_601,
        "first_timestamp": "2025-01-01T00:00:00Z",
        "last_timestamp": "2026-01-01T00:00:00Z",
        "panel_sha256": DIGEST,
        "panel_uri": "file:///lake/canonical/perp/bybit/BTCUSDT/timeframe=1m/research_panel.parquet",
        "byte_size": 1024,
        "schema_digest": "c" * 64,
        "quality": {
            "null_counts": {},
            "duplicate_timestamp_count": 0,
            "gap_count": 0,
            "missing_bar_count": 0,
            "out_of_order_timestamp_count": 0,
            "non_finite_value_count": 0,
            "non_positive_price_count": 0,
            "negative_volume_count": 0,
            "invalid_ohlc_geometry_count": 0,
        },
        "instrument_reference": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "settle_asset": "USDT",
            "price_precision": 1,
            "qty_precision": 3,
        },
        "recovery_copy": {
            "uri": f"file:///recovery/{DIGEST}.parquet",
            "content_digest": DIGEST,
            "byte_size": 1024,
            "integrity_verified": True,
            "scope": "same-host immutable recovery copy; not disaster recovery",
        },
        "checks": {
            "canonical_path": True,
            "complete_one_minute_grid": True,
            "duplicate_timestamps": True,
            "fetch_records_successful": True,
        },
        "coverage_records": [{}],
        "fetch_records": [{}],
        "manifest_digests": {
            "coverage": "d" * 64,
            "fetch_state": "e" * 64,
            "instruments": "f" * 64,
        },
        "claim_boundary": "Local exchange-labelled history only.",
    }
    return {
        "schema_version": "bulletproof-producer-receipt-v1.0.0",
        "milestone": "ALPHA-001",
        "producer": "bt.institutional.alpha.real_data_admission_receipt",
        "producer_version": "2.0.0",
        "source_commit": COMMIT,
        "input_digest": "1" * 64,
        "dataset_digest": DIGEST,
        "configuration_digest": "2" * 64,
        "artifact_digest": "3" * 64,
        "result_digest": "4" * 64,
        "result": result,
        "authority": {
            "allocation": False,
            "capital": False,
            "orders": False,
            "promotion": False,
        },
        "receipt_digest": "5" * 64,
    }


def test_selected_panel_receipt_materializes_exact_data_registry(monkeypatch):
    captured = {}

    def register(name, record):
        def apply(_db, payload):
            captured[name] = payload
            return SimpleNamespace(
                id=uuid4(),
                snapshot_digest=getattr(payload, "snapshot_digest", None),
                manifest_digest=getattr(payload, "manifest_digest", None),
                catalog_digest=getattr(payload, "catalog_digest", None),
            )

        return apply

    quantitative = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_receipt",
        lambda _db, _payload: quantitative,
    )
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_reference_snapshot",
        register("reference", None),
    )
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_manifest",
        register("manifest", None),
    )
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_build",
        register("build", None),
    )
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_catalog",
        register("catalog", None),
    )
    monkeypatch.setattr(
        "app.services.alpha_data_admission.register_lake_governance",
        register("governance", None),
    )
    binding = register_selected_panel_receipt(
        MagicMock(),
        receipt_document=receipt(),
        registered_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert binding.producer_receipt_id == quantitative.id
    assert binding.partition_digests == [DIGEST]
    assert binding.evidence_class == "live_exchange_history"
    assert captured["manifest"].manifest.source_objects[0].sha256 == DIGEST
    assert captured["build"].output_uri == f"file:///recovery/{DIGEST}.parquet"
    assert {item.check: item.observed for item in captured["build"].quality_results} == {
        "duplicate_timestamp_count": 0,
        "missing_bar_count": 0,
        "non_finite_value_count": 0,
        "non_positive_price_count": 0,
        "out_of_order_timestamp_count": 0,
        "negative_volume_count": 0,
        "invalid_ohlc_geometry_count": 0,
    }
    assert captured["catalog"].catalog.partitions[0].gap_count == 0
    governance = captured["governance"].snapshot
    assert governance.entitlements[0].actions == ["read"]
    assert governance.recovery_manifests[0].integrity_verified is True
    assert governance.observed_storage_bytes[binding.dataset_key] == 1024
