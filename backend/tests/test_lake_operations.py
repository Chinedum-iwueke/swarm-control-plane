from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.lake_operations import router
from app.schemas.lake_operations import (
    LakeAdmissionRequest,
    LakeGovernanceContract,
    LakeGovernanceCreate,
    PublicationActionRequest,
    RestoreRequest,
)
from app.schemas.market_data_catalog import ImmutableMarketDataCatalog
from app.services.lake_operations import (
    LakeOperationConflict,
    disable_publication,
    evaluate_admission,
    register_lake_governance,
    restore_publication,
)
from app.services.research import record_digest
from pydantic import ValidationError

NOW = datetime(2026, 8, 27, tzinfo=UTC)
CATALOG_DIGEST = "a" * 64
PARTITION_DIGEST = "b" * 64
SCHEMA_DIGEST = "c" * 64
OUTPUT_DIGEST = "d" * 64
TRANSFORM_DIGEST = "e" * 64
BACKUP_DIGEST = "f" * 64


def catalog() -> ImmutableMarketDataCatalog:
    return ImmutableMarketDataCatalog.model_validate(
        {
            "schema_version": 1,
            "as_of": NOW,
            "reference_snapshot_digest": "1" * 64,
            "partitions": [
                {
                    "partition_id": "btc-r1",
                    "partition_key": "btc-202608",
                    "dataset_key": "binance-perpetual-klines",
                    "layer": "raw",
                    "source_key": "binance-archive",
                    "venue_id": "binance",
                    "instrument_id": "crypto:btc-usdt-perpetual",
                    "listing_id": "binance:btc-perpetual",
                    "timeframe": "1h",
                    "uri": "fixture://data003/btc.parquet",
                    "access_mode": "read_only",
                    "content_digest": PARTITION_DIGEST,
                    "schema_digest": SCHEMA_DIGEST,
                    "rows": 24,
                    "duplicate_count": 0,
                    "gap_count": 0,
                    "event_start": NOW - timedelta(days=2),
                    "event_end": NOW - timedelta(days=1),
                    "observed_at": NOW - timedelta(days=1),
                    "available_at": NOW - timedelta(days=1) + timedelta(minutes=1),
                    "revision_id": "partition-r1",
                }
            ],
            "source_availability": [
                {
                    "availability_id": "availability-r1",
                    "source_key": "binance-archive",
                    "status": "available",
                    "coverage_start": NOW - timedelta(days=2),
                    "coverage_end": NOW - timedelta(days=1),
                    "observed_at": NOW - timedelta(days=1),
                    "available_at": NOW - timedelta(days=1) + timedelta(minutes=1),
                    "revision_id": "availability-r1",
                }
            ],
        }
    )


def contract(**updates) -> LakeGovernanceContract:
    document = {
        "schema_version": 1,
        "as_of": NOW,
        "catalog_digest": CATALOG_DIGEST,
        "quality_slos": [
            {
                "dataset_key": "binance-perpetual-klines",
                "layer": "raw",
                "maximum_freshness_seconds": 172800,
                "maximum_duplicate_count": 0,
                "maximum_gap_count": 0,
                "expected_schema_digest": SCHEMA_DIGEST,
            }
        ],
        "lineage_edges": [
            {
                "edge_id": "raw-to-curated-r1",
                "input_digest": PARTITION_DIGEST,
                "output_digest": OUTPUT_DIGEST,
                "transformation_digest": TRANSFORM_DIGEST,
                "transformation_name": "normalize-bars-v1",
            }
        ],
        "entitlements": [
            {
                "rule_id": "research-read-r1",
                "principal": "research-runner",
                "dataset_keys": ["binance-perpetual-klines"],
                "actions": ["read", "delete"],
                "purpose": "systematic-research",
                "valid_from": NOW - timedelta(days=30),
            }
        ],
        "storage_budgets": [
            {
                "budget_key": "binance-budget-r1",
                "dataset_key": "binance-perpetual-klines",
                "maximum_bytes": 1000,
                "warning_percent": 80,
            }
        ],
        "observed_storage_bytes": {"binance-perpetual-klines": 500},
        "retention_holds": [
            {
                "hold_id": "legal-hold-r1",
                "object_digest": PARTITION_DIGEST,
                "reason_code": "research-reproducibility",
                "active_from": NOW - timedelta(days=1),
            }
        ],
        "recovery_manifests": [
            {
                "recovery_key": "catalog-backup-r1",
                "backup_digest": BACKUP_DIGEST,
                "catalog_digest": CATALOG_DIGEST,
                "object_digests": [PARTITION_DIGEST],
                "created_at": NOW - timedelta(hours=1),
                "integrity_verified": True,
                "verifier": "lake-operator",
            }
        ],
        "publications": [
            {
                "publication_key": "btc-curated-r1",
                "publication_digest": OUTPUT_DIGEST,
                "catalog_digest": CATALOG_DIGEST,
                "output_digests": [OUTPUT_DIGEST],
            }
        ],
    }
    document.update(updates)
    return LakeGovernanceContract.model_validate(document)


def admission(**updates) -> LakeAdmissionRequest:
    document = {
        "snapshot_digest": "9" * 64,
        "partition_digest": PARTITION_DIGEST,
        "principal": "research-runner",
        "action": "read",
        "purpose": "systematic-research",
        "evaluated_at": NOW,
        "observed_schema_digest": SCHEMA_DIGEST,
        "duplicate_count": 0,
        "gap_count": 0,
        "last_available_at": NOW - timedelta(hours=1),
    }
    document.update(updates)
    return LakeAdmissionRequest.model_validate(document)


def records(value: LakeGovernanceContract | None = None):
    value = value or contract()
    governance = SimpleNamespace(
        id=uuid4(), snapshot=value.model_dump(mode="json"), snapshot_digest="9" * 64
    )
    catalog_value = catalog()
    catalog_record = SimpleNamespace(catalog=catalog_value.model_dump(mode="json"))
    return governance, catalog_record


def decision_db(value=None):
    governance, catalog_record = records(value)
    db = MagicMock()
    db.scalar.side_effect = [governance, catalog_record, None, None]
    return db


def test_clean_read_admission_is_allowed_and_metadata_only() -> None:
    result = evaluate_admission(decision_db(), admission())
    assert result.allowed is True
    assert result.quality_passed is True
    assert result.entitlement_passed is True
    assert "protected" in result.claim_boundary


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"observed_schema_digest": "2" * 64}, "schema_mismatch"),
        ({"duplicate_count": 1}, "duplicate_limit_exceeded"),
        ({"gap_count": 1}, "gap_limit_exceeded"),
        ({"last_available_at": NOW - timedelta(days=3)}, "stale_data"),
    ],
)
def test_corrupt_or_stale_partition_is_denied(updates, reason) -> None:
    result = evaluate_admission(decision_db(), admission(**updates))
    assert result.allowed is False
    assert reason in result.reason_codes


def test_unknown_principal_is_denied_by_default() -> None:
    result = evaluate_admission(decision_db(), admission(principal="unknown-runner"))
    assert result.allowed is False
    assert result.reason_codes == ["entitlement_denied"]


def test_retention_hold_blocks_deletion_but_not_read() -> None:
    deleted = evaluate_admission(decision_db(), admission(action="delete"))
    assert deleted.allowed is False
    assert deleted.retention_hold_active is True
    assert "retention_hold" in deleted.reason_codes
    read = evaluate_admission(decision_db(), admission())
    assert read.allowed is True


def test_capacity_pressure_warns_then_fails_closed() -> None:
    warning = contract(observed_storage_bytes={"binance-perpetual-klines": 850})
    result = evaluate_admission(decision_db(warning), admission())
    assert result.allowed is True
    assert result.storage_state == "warning"
    exhausted = contract(observed_storage_bytes={"binance-perpetual-klines": 1000})
    result = evaluate_admission(decision_db(exhausted), admission())
    assert result.allowed is False
    assert result.storage_state == "exhausted"


def test_registration_verifies_catalog_lineage_and_recovery_objects() -> None:
    value = contract()
    payload = LakeGovernanceCreate(
        snapshot_key="DATA003-LAKE-R1",
        snapshot=value,
        snapshot_digest=record_digest(value),
        registered_by="data003-pilot",
    )
    catalog_record = SimpleNamespace(catalog=catalog().model_dump(mode="json"))
    db = MagicMock()
    db.scalar.side_effect = [catalog_record, None]
    record = register_lake_governance(db, payload)
    assert record.catalog_digest == CATALOG_DIGEST
    broken = value.model_copy(
        update={
            "lineage_edges": [
                value.lineage_edges[0].model_copy(update={"input_digest": "8" * 64})
            ]
        }
    )
    db = MagicMock()
    db.scalar.return_value = catalog_record
    with pytest.raises(LakeOperationConflict, match="Lineage input"):
        register_lake_governance(
            db,
            payload.model_copy(
                update={"snapshot": broken, "snapshot_digest": record_digest(broken)}
            ),
        )


def test_disable_and_verified_restore_are_append_only() -> None:
    governance, catalog_record = records()
    disabled_event = SimpleNamespace(
        event_type="publication_disabled", event_digest="7" * 64
    )
    db = MagicMock()
    db.scalar.side_effect = [governance, catalog_record, None, None]
    disabled = disable_publication(
        db,
        PublicationActionRequest(
            snapshot_digest="9" * 64,
            publication_key="btc-curated-r1",
            acted_by="lake-operator",
            reason_code="quality-incident",
        ),
    )
    assert disabled.state == "disabled"
    db = MagicMock()
    db.scalar.side_effect = [
        governance,
        catalog_record,
        disabled_event,
        disabled_event,
        None,
    ]
    restored = restore_publication(
        db,
        RestoreRequest(
            snapshot_digest="9" * 64,
            publication_key="btc-curated-r1",
            recovery_key="catalog-backup-r1",
            restored_catalog_digest=CATALOG_DIGEST,
            restored_object_digests=[PARTITION_DIGEST],
            acted_by="lake-operator",
        ),
    )
    assert restored.state == "restored"


def test_restore_rejects_unverified_or_incomplete_manifest() -> None:
    value = contract()
    unverified = value.recovery_manifests[0].model_copy(
        update={"integrity_verified": False}
    )
    value = value.model_copy(update={"recovery_manifests": [unverified]})
    governance, catalog_record = records(value)
    db = MagicMock()
    db.scalar.side_effect = [governance, catalog_record]
    with pytest.raises(LakeOperationConflict, match="not integrity verified"):
        restore_publication(
            db,
            RestoreRequest(
                snapshot_digest="9" * 64,
                publication_key="btc-curated-r1",
                recovery_key="catalog-backup-r1",
                restored_catalog_digest=CATALOG_DIGEST,
                restored_object_digests=[PARTITION_DIGEST],
                acted_by="lake-operator",
            ),
        )


def test_protected_payload_cannot_enter_governance_contract() -> None:
    document = contract().model_dump()
    document["protected_source_payload"] = "secret rows"
    with pytest.raises(ValidationError, match="Extra inputs"):
        LakeGovernanceContract.model_validate(document)


def test_routes_expose_snapshot_admission_recovery_and_events() -> None:
    paths = {route.path for route in router.routes}
    assert "/v1/research/lake-operations/snapshots" in paths
    assert "/v1/research/lake-operations/admissions" in paths
    assert "/v1/research/lake-operations/publications/restore" in paths
    assert "/v1/research/lake-operations/events" in paths
