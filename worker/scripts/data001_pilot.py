#!/usr/bin/env python3
"""Register and replay a no-capital DATA-001 temporal identity fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx


def canonical_digest(document: Any) -> str:
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def temporal(revision: str, start: str, end: str | None = None) -> dict:
    return {
        "valid_from": start,
        "valid_to": end,
        "observed_at": "2023-12-31T00:00:00Z"
        if start == "2024-01-01T00:00:00Z"
        else "2024-12-20T00:00:00Z",
        "available_at": "2023-12-31T00:00:00Z"
        if start == "2024-01-01T00:00:00Z"
        else "2024-12-20T00:00:00Z",
        "revision_id": revision,
        "corrects_revision_id": None,
    }


def fixture() -> dict:
    old = temporal("listing-r1", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
    current = temporal("listing-r2", "2025-01-01T00:00:00Z")
    current["corrects_revision_id"] = "listing-r1"
    old_instrument = temporal(
        "instrument-r1", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"
    )
    current_instrument = temporal("instrument-r2", "2025-01-01T00:00:00Z")
    current_instrument["corrects_revision_id"] = "instrument-r1"
    base_listing = {
        "listing_id": "binance:btc-perpetual",
        "instrument_id": "crypto:btc-usdt-perpetual",
        "venue_id": "binance",
        "status": "active",
        "price_increment": 0.1,
        "quantity_increment": 0.001,
        "contract_multiplier": 1.0,
    }
    base_instrument = {
        "instrument_id": "crypto:btc-usdt-perpetual",
        "asset_class": "crypto_perpetual",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "settlement_asset": "USDT",
        "contract_type": "perpetual",
        "expiry_at": None,
    }
    return {
        "schema_version": 1,
        "as_of": "2026-08-27T00:00:00Z",
        "source": "data001-pilot",
        "source_revision": "fixture-r1",
        "venues": [
            {
                "venue_id": "binance",
                "name": "Binance",
                "mic": None,
                "timezone": "UTC",
                "calendar_id": "crypto-utc",
                **temporal("venue-r1", "2024-01-01T00:00:00Z"),
            }
        ],
        "instruments": [
            {**base_instrument, **old_instrument},
            {**base_instrument, **current_instrument},
        ],
        "listings": [
            {**base_listing, "symbol": "BTCUSDT", **old},
            {**base_listing, "symbol": "BTCUSDT-PERP", **current},
        ],
        "calendars": [
            {
                "calendar_id": "crypto-utc",
                "timezone": "UTC",
                "sessions": [
                    {"weekday": day, "opens_at": "00:00:00", "closes_at": "00:00:00"}
                    for day in range(7)
                ],
                "holidays": ["2025-01-20"],
                **temporal("calendar-r1", "2024-01-01T00:00:00Z"),
            }
        ],
        "corporate_actions": [
            {
                "action_id": "binance:btc-symbol-change-2025",
                "instrument_id": "crypto:btc-usdt-perpetual",
                "action_type": "symbol_change",
                "effective_at": "2025-01-01T00:00:00Z",
                "announced_at": "2024-12-20T00:00:00Z",
                "available_at": "2024-12-20T00:00:00Z",
                "terms": {
                    "old_symbol": "BTCUSDT",
                    "new_symbol": "BTCUSDT-PERP",
                },
                "revision_id": "action-r1",
            }
        ],
    }


def request(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def resolve(client: httpx.Client, symbol: str, effective_at: str, digest: str):
    return request(
        client,
        "POST",
        "/v1/research/reference-data/resolve",
        json={
            "venue_id": "binance",
            "symbol": symbol,
            "effective_at": effective_at,
            "known_at": "2026-08-27T00:00:00Z",
            "snapshot_digest": digest,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/data001/report.json"),
    )
    args = parser.parse_args()
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    document = fixture()
    digest = canonical_digest(document)
    payload = {
        "snapshot_key": "DATA001-BINANCE-BTC-FIXTURE-R1",
        "snapshot": document,
        "snapshot_digest": digest,
        "supersedes_snapshot_id": None,
        "registered_by": "data001-pilot",
    }
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    ) as client:
        created = client.post("/v1/research/reference-data/snapshots", json=payload)
        if created.status_code == 409:
            snapshots = request(
                client, "GET", "/v1/research/reference-data/snapshots"
            )
            registered = next(
                item for item in snapshots if item["snapshot_key"] == payload["snapshot_key"]
            )
            if registered["snapshot_digest"] != digest:
                raise RuntimeError("Existing DATA-001 fixture has a different digest.")
        else:
            created.raise_for_status()
            registered = created.json()
        prior = resolve(client, "BTCUSDT", "2024-06-01T12:00:00Z", digest)
        current = resolve(client, "BTCUSDT-PERP", "2025-02-01T12:00:00Z", digest)
        holiday = resolve(client, "BTCUSDT-PERP", "2025-01-20T12:00:00Z", digest)
        unknown = client.post(
            "/v1/research/reference-data/resolve",
            json={
                "venue_id": "bybit",
                "symbol": "BTCUSDT",
                "effective_at": "2025-02-01T12:00:00Z",
                "known_at": "2026-08-27T00:00:00Z",
                "snapshot_digest": digest,
            },
        )
        if unknown.status_code != 404:
            raise RuntimeError("Unknown venue identity did not fail closed.")
    checks = {
        "stable_identity_across_symbol_change": prior["instrument"]["instrument_id"]
        == current["instrument"]["instrument_id"],
        "old_symbol_replays_old_revision": prior["listing"]["revision_id"]
        == "listing-r1",
        "new_symbol_replays_new_revision": current["listing"]["revision_id"]
        == "listing-r2",
        "known_action_replayed": len(current["known_corporate_actions"]) == 1,
        "holiday_closed": holiday["session_open"] is False,
        "unknown_identity_failed_closed": unknown.status_code == 404,
        "snapshot_digest_bound": current["snapshot_digest"] == digest,
    }
    report = {
        "schema_version": "data001-pilot-report-v1.0.0",
        "success": all(checks.values()),
        "checks": checks,
        "snapshot_id": registered["id"],
        "snapshot_digest": digest,
        "capital_or_order_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
