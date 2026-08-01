from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.schemas.data_contract import (
    CorporateActionPolicy,
    DatasetBuildCreate,
    DatasetManifestCreate,
    FeatureDefinition,
    PointInTimeDatasetManifest,
    ProviderIdentity,
    QualityAssertion,
    QualityResult,
    SourceObject,
    TransformationStep,
)
from app.services.data_contracts import register_manifest
from app.services.research import record_digest
from pydantic import ValidationError

START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)
AS_OF = datetime(2026, 1, 2, tzinfo=UTC)


def manifest(**updates) -> PointInTimeDatasetManifest:
    document = {
        "schema_version": 1,
        "provider": ProviderIdentity(
            name="binance",
            dataset="futures-klines",
            venue="binance",
            asset_class="crypto-perpetual",
            retrieval_method="local_canonical_store",
            terms_version="2026-08-01",
        ),
        "instruments": ["BTCUSDT"],
        "timeframe": "1h",
        "date_start": START,
        "date_end": END,
        "as_of": AS_OF,
        "timezone": "UTC",
        "source_objects": [
            SourceObject(
                uri="bulletproof://canonical/BTCUSDT/ohlcv.parquet",
                sha256="a" * 64,
                observed_at=END,
                available_at=END + timedelta(minutes=5),
                revision_id="sha256-a",
                rows=525_600,
            )
        ],
        "revision_policy": "exact_revision",
        "fallback_policy": "forbidden",
        "fallback_provider": None,
        "fallback_reason": None,
        "corporate_actions": CorporateActionPolicy(
            mode="not_applicable",
            description="Crypto perpetual bars have no equity corporate actions.",
        ),
        "transformations": [
            TransformationStep(
                order=1,
                name="hourly-ohlcv",
                operation="UTC hourly OHLCV aggregation over complete source rows",
                parameters={"closed": "left"},
                input_columns=["ts", "open", "high", "low", "close", "volume"],
                output_columns=["ts", "open", "high", "low", "close", "volume"],
            )
        ],
        "features": [
            FeatureDefinition(
                feature_key="lagged-return-1",
                expression="close[t-1] / close[t-2] - 1",
                input_columns=["close"],
                lookback_bars=2,
                availability_lag_bars=1,
                null_policy="drop",
            )
        ],
        "output_columns": [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "lagged_return_1",
        ],
        "quality_assertions": [
            QualityAssertion(check="duplicate_timestamp_count", maximum=0),
            QualityAssertion(check="missing_bar_count", maximum=0),
        ],
    }
    document.update(updates)
    return PointInTimeDatasetManifest.model_validate(document)


def test_manifest_preserves_provider_as_of_and_feature_lineage() -> None:
    value = manifest()
    assert value.provider.name == "binance"
    assert value.as_of == AS_OF
    assert value.features[0].availability_lag_bars == 1
    assert value.fallback_policy == "forbidden"


def test_source_unavailable_at_as_of_is_rejected() -> None:
    source = (
        manifest()
        .source_objects[0]
        .model_copy(update={"available_at": AS_OF + timedelta(seconds=1)})
    )
    with pytest.raises(ValidationError, match="availability cannot exceed as_of"):
        manifest(source_objects=[source])


def test_transformation_order_must_be_explicit() -> None:
    step = manifest().transformations[0].model_copy(update={"order": 2})
    with pytest.raises(ValidationError, match="contiguous"):
        manifest(transformations=[step])


def test_silent_provider_fallback_is_rejected() -> None:
    fallback = manifest().provider.model_copy(update={"name": "other-provider"})
    with pytest.raises(ValidationError, match="forbidden fallback"):
        manifest(fallback_provider=fallback)


def test_raw_corporate_actions_require_digest() -> None:
    with pytest.raises(ValidationError, match="requires events_digest"):
        CorporateActionPolicy(
            mode="raw_with_events",
            description="Raw equity prices require separately bound events.",
        )


def test_independent_rebuild_must_match_and_quality_must_pass() -> None:
    common = {
        "build_key": "M15-BTC-1H-2025",
        "manifest_id": uuid4(),
        "builder_repository": "swarm-control-plane",
        "builder_commit": "b" * 40,
        "builder_runtime": "python-3.11-pandas-3.0.0",
        "output_uri": "worker/research-data/m15/btcusdt-1h-2025.csv",
        "rows": 8760,
        "started_at": START,
        "ended_at": START + timedelta(seconds=1),
        "content_digest": "c" * 64,
        "rebuild_content_digest": "d" * 64,
        "quality_results": [
            QualityResult(
                check="duplicate_timestamp_count",
                observed=0,
                maximum=0,
                passed=True,
            )
        ],
        "record_digest": "e" * 64,
        "built_by": "m15-data-builder",
    }
    with pytest.raises(ValidationError, match="rebuild digest"):
        DatasetBuildCreate.model_validate(common)
    common["rebuild_content_digest"] = common["content_digest"]
    common["quality_results"] = [
        {
            "check": "missing_bar_count",
            "observed": 1,
            "maximum": 0,
            "passed": False,
        }
    ]
    with pytest.raises(ValidationError, match="quality checks must pass"):
        DatasetBuildCreate.model_validate(common)


def test_manifest_digest_is_verified_before_storage() -> None:
    value = manifest()
    db = MagicMock()
    db.scalar.return_value = None
    payload = DatasetManifestCreate(
        manifest_key="M15-BTC-1H-2025",
        manifest=value,
        manifest_digest=record_digest(value),
        registered_by="research-registry",
    )
    record = register_manifest(db, payload)
    assert record.manifest_digest == payload.manifest_digest
    db.add.assert_called_once_with(record)
    db.flush.assert_called_once()
