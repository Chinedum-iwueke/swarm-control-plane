from __future__ import annotations

from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_contract import ResearchDatasetBuild
from app.models.lake_operations import LakeGovernanceSnapshot
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.schemas.alpha_campaign import AlphaDatasetBinding
from app.schemas.data_contract import (
    DatasetBuildCreate,
    DatasetManifestCreate,
    PointInTimeDatasetManifest,
)
from app.schemas.lake_operations import LakeGovernanceContract, LakeGovernanceCreate
from app.schemas.market_data_catalog import (
    ImmutableMarketDataCatalog,
    MarketDataCatalogCreate,
)
from app.schemas.quantitative_receipt import QuantitativeReceiptCreate
from app.schemas.reference_data import (
    PointInTimeReferenceSnapshot,
    ReferenceSnapshotCreate,
)
from app.services.data_contracts import register_build, register_manifest
from app.services.lake_operations import register_lake_governance
from app.services.market_data_catalog import register_catalog
from app.services.quantitative_receipt import register_receipt
from app.services.reference_data import register_reference_snapshot
from app.services.research import record_digest


class AlphaDataAdmissionConflict(ValueError):
    """A native selected-panel receipt cannot be promoted into DATA registries."""


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AlphaDataAdmissionConflict("Admission timestamps must be timezone aware.")
    return parsed.astimezone(UTC)


def _positive_increment(reference: dict, field: str, precision: str) -> float:
    raw = reference.get(field)
    if raw not in (None, ""):
        value = float(raw)
    else:
        value = 10.0 ** -int(reference.get(precision, 0))
    if value <= 0:
        raise AlphaDataAdmissionConflict(f"Instrument {field} must be positive.")
    return value


def register_selected_panel_receipt(
    db: Session,
    *,
    receipt_document: dict,
    registered_at: datetime,
) -> AlphaDatasetBinding:
    """Register one content-admitted panel through DATA-001/002/003.

    The native receipt remains authoritative for file bytes and quality. These
    records make its exact identity, availability, entitlement, and recovery
    boundary queryable by the governed campaign service.
    """

    registered_at = registered_at.astimezone(UTC)
    quantitative = register_receipt(
        db,
        QuantitativeReceiptCreate.model_validate(
            {"receipt": receipt_document, "registered_by": "alpha-data-admission"}
        ),
    )
    result = receipt_document.get("result", {})
    if (
        result.get("schema_version") != "alpha001-real-data-admission-v2.0.0"
        or result.get("admitted") is not True
        or result.get("evidence_class") != "live_exchange_history"
        or result.get("recovery_copy", {}).get("integrity_verified") is not True
        or any(value is not True for value in result.get("checks", {}).values())
    ):
        raise AlphaDataAdmissionConflict(
            "Only complete ALPHA-001 v2 selected-panel receipts may be registered."
        )

    venue = str(result["venue"]).lower()
    symbol = str(result["instrument"]).upper()
    timeframe = str(result["timeframe"])
    panel_digest = str(result["panel_sha256"])
    schema_digest = str(result["schema_digest"])
    reference = result["instrument_reference"]
    first = _timestamp(result["first_timestamp"])
    last = _timestamp(result["last_timestamp"])
    key_suffix = panel_digest[:12]
    dataset_key = f"alpha-{venue}-{symbol.lower()}-perp-{timeframe}-{key_suffix}"
    build_key = f"alpha-build-{venue}-{symbol.lower()}-{key_suffix}"
    catalog_key = f"alpha-catalog-{venue}-{symbol.lower()}-{key_suffix}"
    governance_key = f"alpha-governance-{venue}-{symbol.lower()}-{key_suffix}"

    # A panel may be selected by more than one campaign. Reuse its complete,
    # content-addressed DATA binding instead of attempting to mint a second
    # timestamp-dependent snapshot under the same immutable keys.
    existing_build = db.scalar(
        select(ResearchDatasetBuild).where(ResearchDatasetBuild.build_key == build_key)
    )
    existing_catalog = db.scalar(
        select(MarketDataCatalogSnapshot).where(
            MarketDataCatalogSnapshot.catalog_key == catalog_key
        )
    )
    existing_governance = db.scalar(
        select(LakeGovernanceSnapshot).where(
            LakeGovernanceSnapshot.snapshot_key == governance_key
        )
    )
    existing = (existing_build, existing_catalog, existing_governance)
    present = [record for record in existing if record is not None]
    if present and all(isinstance(record.id, UUID) for record in present):
        if any(record is None for record in existing):
            raise AlphaDataAdmissionConflict(
                "Selected panel has an incomplete existing DATA binding."
            )
        partitions = existing_catalog.catalog.get("partitions", [])
        if (
            existing_build.content_digest != panel_digest
            or len(partitions) != 1
            or partitions[0].get("content_digest") != panel_digest
            or existing_governance.catalog_digest != existing_catalog.catalog_digest
        ):
            raise AlphaDataAdmissionConflict(
                "Selected panel existing DATA binding changed content."
            )
        return AlphaDatasetBinding(
            dataset_build_id=existing_build.id,
            catalog_id=existing_catalog.id,
            lake_governance_snapshot_id=existing_governance.id,
            producer_receipt_id=quantitative.id,
            dataset_key=dataset_key,
            partition_digests=[panel_digest],
            evidence_class="live_exchange_history",
            research_principal="alpha-research-runner",
        )
    instrument_id = f"crypto:{symbol.lower()}-perpetual"
    listing_id = f"{venue}:{symbol.lower()}-perpetual"
    source_key = f"{venue}-local-canonical"
    revision = f"sha256-{key_suffix}"
    base_asset = str(reference.get("base_asset") or "").upper()
    quote_asset = str(reference.get("quote_asset") or "").upper()
    settlement_asset = str(
        reference.get("settle_asset") or reference.get("settlement_asset") or ""
    ).upper()
    if not all((base_asset, quote_asset, settlement_asset)):
        raise AlphaDataAdmissionConflict(
            "Instrument manifest lacks base, quote, or settlement identity."
        )

    def temporal(kind: str) -> dict:
        return {
            "valid_from": first,
            "observed_at": last,
            "available_at": last,
            "revision_id": f"{kind}-{key_suffix}",
        }

    snapshot = PointInTimeReferenceSnapshot.model_validate(
        {
            "schema_version": 1,
            "as_of": registered_at,
            "source": "alpha-data-admission",
            "source_revision": revision,
            "venues": [
                {
                    "venue_id": venue,
                    "name": venue.capitalize(),
                    "timezone": "UTC",
                    "calendar_id": "crypto-utc",
                    **temporal("venue"),
                }
            ],
            "instruments": [
                {
                    "instrument_id": instrument_id,
                    "asset_class": "crypto_perpetual",
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "settlement_asset": settlement_asset,
                    "contract_type": "perpetual",
                    **temporal("instrument"),
                }
            ],
            "listings": [
                {
                    "listing_id": listing_id,
                    "instrument_id": instrument_id,
                    "venue_id": venue,
                    "symbol": symbol,
                    "status": "active",
                    "price_increment": _positive_increment(
                        reference, "tick_size", "price_precision"
                    ),
                    "quantity_increment": _positive_increment(
                        reference, "qty_step", "qty_precision"
                    ),
                    "contract_multiplier": 1.0,
                    **temporal("listing"),
                }
            ],
            "calendars": [
                {
                    "calendar_id": "crypto-utc",
                    "timezone": "UTC",
                    "sessions": [
                        {"weekday": day, "opens_at": time(0), "closes_at": time(0)}
                        for day in range(7)
                    ],
                    "holidays": [],
                    **temporal("calendar"),
                }
            ],
            "corporate_actions": [],
        }
    )
    reference_record = register_reference_snapshot(
        db,
        ReferenceSnapshotCreate(
            snapshot_key=f"alpha-reference-{venue}-{symbol.lower()}-{key_suffix}",
            snapshot=snapshot,
            snapshot_digest=record_digest(snapshot),
            registered_by="alpha-data-admission",
        ),
    )

    manifest_document = PointInTimeDatasetManifest.model_validate(
        {
            "schema_version": 1,
            "provider": {
                "name": venue,
                "dataset": dataset_key,
                "venue": venue,
                "asset_class": "crypto-perpetual",
                "retrieval_method": "local_canonical_store",
                "terms_version": "native-acquisition-manifest",
            },
            "instruments": [symbol],
            "reference_snapshot_digest": reference_record.snapshot_digest,
            "instrument_reference_bindings": [
                {
                    "requested_instrument": symbol,
                    "venue_id": venue,
                    "instrument_id": instrument_id,
                    "listing_id": listing_id,
                }
            ],
            "timeframe": timeframe,
            "date_start": first,
            "date_end": last,
            "as_of": registered_at,
            "timezone": "UTC",
            "source_objects": [
                {
                    "uri": result["panel_uri"],
                    "sha256": panel_digest,
                    "observed_at": last,
                    "available_at": last,
                    "revision_id": revision,
                    "rows": result["row_count"],
                }
            ],
            "revision_policy": "exact_revision",
            "fallback_policy": "forbidden",
            "corporate_actions": {
                "mode": "not_applicable",
                "description": "Crypto perpetual bars have no equity corporate actions.",
            },
            "transformations": [
                {
                    "order": 1,
                    "name": "canonical-panel-verification",
                    "operation": "Retain the exact native canonical one-minute panel after deterministic quality checks.",
                    "parameters": {"content_digest": panel_digest},
                    "input_columns": ["ts", "open", "high", "low", "close", "volume"],
                    "output_columns": ["ts", "open", "high", "low", "close", "volume"],
                }
            ],
            "features": [
                {
                    "feature_key": "observed-close",
                    "expression": "close[t]",
                    "input_columns": ["close"],
                    "lookback_bars": 0,
                    "availability_lag_bars": 0,
                    "null_policy": "preserve",
                }
            ],
            "output_columns": ["ts", "open", "high", "low", "close", "volume"],
            "quality_assertions": [
                {"check": "duplicate_timestamp_count", "maximum": 0},
                {"check": "missing_bar_count", "maximum": 0},
                {"check": "non_finite_value_count", "maximum": 0},
                {"check": "non_positive_price_count", "maximum": 0},
                {"check": "out_of_order_timestamp_count", "maximum": 0},
            ],
        }
    )
    manifest_record = register_manifest(
        db,
        DatasetManifestCreate(
            manifest_key=f"alpha-manifest-{venue}-{symbol.lower()}-{key_suffix}",
            manifest=manifest_document,
            manifest_digest=record_digest(manifest_document),
            registered_by="alpha-data-admission",
        ),
    )
    build_core = {
        "build_key": build_key,
        "manifest_id": manifest_record.id,
        "builder_repository": "bulletproof_bt",
        "builder_commit": receipt_document["source_commit"],
        "builder_runtime": "native-selected-panel-hash-and-quality-verification",
        "output_uri": result["recovery_copy"]["uri"],
        "rows": result["row_count"],
        "started_at": registered_at,
        "ended_at": registered_at,
        "content_digest": panel_digest,
        "rebuild_content_digest": result["recovery_copy"]["content_digest"],
        "quality_results": [
            {
                "check": key,
                "observed": int(result["quality"][key]),
                "maximum": 0,
                "passed": int(result["quality"][key]) == 0,
            }
            for key in (
                "duplicate_timestamp_count",
                "missing_bar_count",
                "non_finite_value_count",
                "non_positive_price_count",
                "out_of_order_timestamp_count",
                "negative_volume_count",
                "invalid_ohlc_geometry_count",
            )
        ],
    }
    build_payload = DatasetBuildCreate.model_validate(
        {
            **build_core,
            "record_digest": "0" * 64,
            "built_by": "alpha-data-admission",
        }
    )
    build_payload = build_payload.model_copy(
        update={
            "record_digest": record_digest(
                build_payload.model_dump(
                    mode="json", exclude={"record_digest", "built_by"}
                )
            )
        }
    )
    build_record = register_build(db, build_payload)

    catalog_document = ImmutableMarketDataCatalog.model_validate(
        {
            "schema_version": 1,
            "as_of": registered_at,
            "reference_snapshot_digest": reference_record.snapshot_digest,
            "partitions": [
                {
                    "partition_id": f"panel-{key_suffix}",
                    "partition_key": f"{venue}-{symbol.lower()}-{timeframe}-{key_suffix}",
                    "dataset_key": dataset_key,
                    "layer": "curated",
                    "source_key": source_key,
                    "venue_id": venue,
                    "instrument_id": instrument_id,
                    "listing_id": listing_id,
                    "timeframe": timeframe,
                    "uri": result["panel_uri"],
                    "access_mode": "read_only",
                    "content_digest": panel_digest,
                    "schema_digest": schema_digest,
                    "rows": result["row_count"],
                    "duplicate_count": 0,
                    "gap_count": 0,
                    "event_start": first,
                    "event_end": last,
                    "observed_at": last,
                    "available_at": last,
                    "revision_id": revision,
                }
            ],
            "memberships": [
                {
                    "membership_id": f"selected-{key_suffix}",
                    "universe_key": "alpha-preregistered-selection",
                    "instrument_id": instrument_id,
                    "effective_from": first,
                    "effective_to": last,
                    "observed_at": last,
                    "available_at": last,
                    "revision_id": f"membership-{key_suffix}",
                }
            ],
            "source_availability": [
                {
                    "availability_id": f"availability-{key_suffix}",
                    "source_key": source_key,
                    "status": "available",
                    "coverage_start": first,
                    "coverage_end": last,
                    "observed_at": last,
                    "available_at": last,
                    "revision_id": f"availability-{key_suffix}",
                }
            ],
        }
    )
    catalog_record = register_catalog(
        db,
        MarketDataCatalogCreate(
            catalog_key=catalog_key,
            catalog=catalog_document,
            catalog_digest=record_digest(catalog_document),
            registered_by="alpha-data-admission",
        ),
    )

    byte_size = int(result["byte_size"])
    governance_document = LakeGovernanceContract.model_validate(
        {
            "schema_version": 1,
            "as_of": registered_at,
            "catalog_digest": catalog_record.catalog_digest,
            "quality_slos": [
                {
                    "dataset_key": dataset_key,
                    "layer": "curated",
                    "maximum_freshness_seconds": 31_536_000,
                    "maximum_duplicate_count": 0,
                    "maximum_gap_count": 0,
                    "expected_schema_digest": schema_digest,
                }
            ],
            "lineage_edges": [],
            "entitlements": [
                {
                    "rule_id": f"alpha-research-read-{key_suffix}",
                    "principal": "alpha-research-runner",
                    "dataset_keys": [dataset_key],
                    "actions": ["read"],
                    "purpose": "research",
                    "valid_from": registered_at,
                }
            ],
            "storage_budgets": [
                {
                    "budget_key": f"alpha-storage-{key_suffix}",
                    "dataset_key": dataset_key,
                    "maximum_bytes": max(1, byte_size * 2),
                    "warning_percent": 90,
                }
            ],
            "observed_storage_bytes": {dataset_key: byte_size},
            "retention_holds": [
                {
                    "hold_id": f"alpha-evidence-{key_suffix}",
                    "object_digest": panel_digest,
                    "reason_code": "active-research-evidence",
                    "active_from": registered_at,
                }
            ],
            "recovery_manifests": [
                {
                    "recovery_key": f"same-host-copy-{key_suffix}",
                    "backup_digest": result["recovery_copy"]["content_digest"],
                    "catalog_digest": catalog_record.catalog_digest,
                    "object_digests": [panel_digest],
                    "created_at": registered_at,
                    "integrity_verified": True,
                    "verifier": "alpha-data-admission",
                }
            ],
            "publications": [],
        }
    )
    governance_record = register_lake_governance(
        db,
        LakeGovernanceCreate(
            snapshot_key=governance_key,
            snapshot=governance_document,
            snapshot_digest=record_digest(governance_document),
            registered_by="alpha-data-admission",
        ),
    )
    return AlphaDatasetBinding(
        dataset_build_id=build_record.id,
        catalog_id=catalog_record.id,
        lake_governance_snapshot_id=governance_record.id,
        producer_receipt_id=quantitative.id,
        dataset_key=dataset_key,
        partition_digests=[panel_digest],
        evidence_class="live_exchange_history",
        research_principal="alpha-research-runner",
    )
