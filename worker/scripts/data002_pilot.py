#!/usr/bin/env python3
"""Register and replay a no-capital DATA-002 market-data catalog fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(document) -> str:
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def catalog(reference_digest: str, *, corrected: bool) -> dict:
    first = {
        "partition_id": "btc-1h-202502-r1",
        "partition_key": "btc-1h-202502",
        "dataset_key": "binance-perpetual-klines",
        "layer": "raw",
        "source_key": "binance-archive",
        "venue_id": "binance",
        "instrument_id": "crypto:btc-usdt-perpetual",
        "listing_id": "binance:btc-perpetual",
        "timeframe": "1h",
        "uri": "fixture://data002/binance/BTCUSDT-PERP/2025-02-r1.parquet",
        "access_mode": "read_only",
        "content_digest": hashlib.sha256(b"data002-original-bars").hexdigest(),
        "schema_digest": hashlib.sha256(b"timestamp,ohlcv-v1").hexdigest(),
        "rows": 672,
        "duplicate_count": 0,
        "gap_count": 0,
        "event_start": "2025-02-01T00:00:00Z",
        "event_end": "2025-03-01T00:00:00Z",
        "observed_at": "2025-03-01T00:00:00Z",
        "available_at": "2025-03-01T00:05:00Z",
        "revision_id": "partition-r1",
        "corrects_revision_id": None,
    }
    partitions = [first]
    if corrected:
        partitions.append(
            {
                **first,
                "partition_id": "btc-1h-202502-r2",
                "uri": "fixture://data002/binance/BTCUSDT-PERP/2025-02-r2.parquet",
                "content_digest": hashlib.sha256(b"data002-corrected-bars").hexdigest(),
                "observed_at": "2025-03-02T00:00:00Z",
                "available_at": "2025-03-02T00:05:00Z",
                "revision_id": "partition-r2",
                "corrects_revision_id": "partition-r1",
            }
        )
    return {
        "schema_version": 1,
        "as_of": "2026-08-26T00:00:00Z" if not corrected else "2026-08-27T00:00:00Z",
        "reference_snapshot_digest": reference_digest,
        "partitions": partitions,
        "memberships": [
            {
                "membership_id": "liquid-btc-r1",
                "universe_key": "liquid-perpetuals",
                "instrument_id": "crypto:btc-usdt-perpetual",
                "effective_from": "2025-01-01T00:00:00Z",
                "effective_to": None,
                "observed_at": "2025-01-01T00:00:00Z",
                "available_at": "2025-01-01T00:00:00Z",
                "revision_id": "membership-r1",
                "corrects_revision_id": None,
            }
        ],
        "source_availability": [
            {
                "availability_id": "binance-archive-r1",
                "source_key": "binance-archive",
                "status": "available",
                "coverage_start": "2025-02-01T00:00:00Z",
                "coverage_end": "2025-03-01T00:00:00Z",
                "observed_at": "2025-03-01T00:00:00Z",
                "available_at": "2025-03-01T00:01:00Z",
                "revision_id": "availability-r1",
                "corrects_revision_id": None,
                "reason": None,
            }
        ],
    }


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def register(client: httpx.Client, key: str, document: dict, supersedes=None):
    content_digest = digest(document)
    response = client.post(
        "/v1/research/market-data-catalog/snapshots",
        json={
            "catalog_key": key,
            "catalog": document,
            "catalog_digest": content_digest,
            "supersedes_catalog_id": supersedes,
            "registered_by": "data002-pilot",
        },
    )
    if response.status_code == 409:
        existing = call(client, "GET", "/v1/research/market-data-catalog/snapshots")
        record = next(item for item in existing if item["catalog_key"] == key)
        if record["catalog_digest"] != content_digest:
            raise RuntimeError("Existing DATA-002 fixture has a different digest.")
        return record
    response.raise_for_status()
    return response.json()


def resolve(client: httpx.Client, catalog_digest: str):
    return call(
        client,
        "POST",
        "/v1/research/market-data-catalog/resolve",
        json={
            "dataset_key": "binance-perpetual-klines",
            "layer": "raw",
            "venue_id": "binance",
            "symbol": "BTCUSDT-PERP",
            "timeframe": "1h",
            "effective_at": "2025-02-15T12:00:00Z",
            "known_at": "2026-08-27T00:00:00Z",
            "universe_key": "liquid-perpetuals",
            "catalog_digest": catalog_digest,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/data002/report.json"),
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=90,
    ) as client:
        references = call(client, "GET", "/v1/research/reference-data/snapshots")
        reference = next(
            item for item in references if item["snapshot_key"].startswith("DATA001-")
        )
        prior_document = catalog(reference["snapshot_digest"], corrected=False)
        prior = register(client, "DATA002-BINANCE-BTC-R1", prior_document)
        current_document = catalog(reference["snapshot_digest"], corrected=True)
        current = register(
            client,
            "DATA002-BINANCE-BTC-R2",
            current_document,
            supersedes=prior["id"],
        )
        prior_resolution = resolve(client, prior["catalog_digest"])
        current_resolution = resolve(client, current["catalog_digest"])
        gap = client.post(
            "/v1/research/market-data-catalog/resolve",
            json={
                "dataset_key": "binance-perpetual-klines",
                "layer": "raw",
                "venue_id": "binance",
                "symbol": "BTCUSDT-PERP",
                "timeframe": "1h",
                "effective_at": "2025-04-01T00:00:00Z",
                "known_at": "2026-08-27T00:00:00Z",
                "catalog_digest": current["catalog_digest"],
            },
        )
    checks = {
        "prior_snapshot_replays_original_revision": prior_resolution["partition"][
            "revision_id"
        ]
        == "partition-r1",
        "superseding_snapshot_replays_correction": current_resolution["partition"][
            "revision_id"
        ]
        == "partition-r2",
        "content_digest_changed_with_correction": prior_resolution["partition"][
            "content_digest"
        ]
        != current_resolution["partition"]["content_digest"],
        "stable_identity_bound": current_resolution["instrument_id"]
        == "crypto:btc-usdt-perpetual",
        "membership_replayed": current_resolution["membership"]["universe_key"]
        == "liquid-perpetuals",
        "source_available": current_resolution["source_availability"]["status"]
        == "available",
        "coverage_gap_failed_closed": gap.status_code == 404,
        "source_access_read_only": current_resolution["partition"]["access_mode"]
        == "read_only",
    }
    report = {
        "schema_version": "data002-pilot-report-v1.0.0",
        "success": all(checks.values()),
        "checks": checks,
        "reference_snapshot_digest": reference["snapshot_digest"],
        "prior_catalog_id": prior["id"],
        "prior_catalog_digest": prior["catalog_digest"],
        "catalog_id": current["id"],
        "catalog_digest": current["catalog_digest"],
        "capital_or_order_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
