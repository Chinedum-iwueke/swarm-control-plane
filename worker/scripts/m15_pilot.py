from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/m15_build_dataset.py"


def digest(document: dict) -> str:
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build(
    python: Path, source: Path, output: Path, instrument: str
) -> tuple[dict, datetime, datetime]:
    started = datetime.now(UTC)
    completed = subprocess.run(
        [
            str(python),
            str(BUILDER),
            "--source",
            str(source),
            "--output",
            str(output),
            "--instrument",
            instrument,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
        env={
            key: value
            for key, value in os.environ.items()
            if key in {"HOME", "LANG", "LC_ALL", "PATH", "VIRTUAL_ENV"}
        },
    )
    ended = datetime.now(UTC)
    return json.loads(completed.stdout), started, ended


def post(client: httpx.Client, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def manifest(instrument: str, result: dict, source: Path, as_of: str) -> dict:
    return {
        "schema_version": 1,
        "provider": {
            "name": "binance",
            "dataset": "futures-klines",
            "venue": "binance",
            "asset_class": "crypto-perpetual",
            "retrieval_method": "local_canonical_store",
            "terms_version": "observed-2026-08-01",
        },
        "instruments": [instrument],
        "timeframe": "1h",
        "date_start": "2025-01-01T00:00:00Z",
        "date_end": "2026-01-01T00:00:00Z",
        "as_of": as_of,
        "timezone": "UTC",
        "source_objects": [
            {
                "uri": f"bulletproof://{source.relative_to(source.parents[5])}",
                "sha256": result["source_digest"],
                "observed_at": result["source_observed_at"],
                "available_at": as_of,
                "revision_id": f"sha256-{result['source_digest'][:24]}",
                "rows": result["source_rows"],
            }
        ],
        "revision_policy": "exact_revision",
        "fallback_policy": "forbidden",
        "fallback_provider": None,
        "fallback_reason": None,
        "corporate_actions": {
            "mode": "not_applicable",
            "events_digest": None,
            "description": (
                "Crypto perpetual OHLCV bars have no equity corporate actions; "
                "contract and funding semantics require separate future contracts."
            ),
        },
        "transformations": [
            {
                "order": 1,
                "name": "bounded-2025-window",
                "operation": "Select UTC timestamps in [2025-01-01, 2026-01-01).",
                "parameters": {"inclusive": "left"},
                "input_columns": ["ts", "open", "high", "low", "close", "volume"],
                "output_columns": ["ts", "open", "high", "low", "close", "volume"],
            },
            {
                "order": 2,
                "name": "hourly-ohlcv",
                "operation": "Aggregate complete one-minute rows into UTC hourly bars.",
                "parameters": {"label": "left", "closed": "left"},
                "input_columns": ["ts", "open", "high", "low", "close", "volume"],
                "output_columns": ["ts", "open", "high", "low", "close", "volume"],
            },
            {
                "order": 3,
                "name": "lagged-return-feature",
                "operation": "Compute prior completed hourly close return and lag once.",
                "parameters": {"lag_bars": 1, "lookback_bars": 2},
                "input_columns": ["close"],
                "output_columns": ["lagged_return_1"],
            },
        ],
        "features": [
            {
                "feature_key": "lagged-return-1",
                "expression": "close[t-1] / close[t-2] - 1",
                "input_columns": ["close"],
                "lookback_bars": 2,
                "availability_lag_bars": 1,
                "null_policy": "drop",
                "null_constant": None,
            }
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
            {"check": name, "maximum": 0} for name in sorted(result["quality"])
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M15 deterministic data pilot")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--bulletproof-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    if len(args.source_commit) != 40:
        raise RuntimeError("A full source commit is required.")
    python = args.bulletproof_root / ".venv/bin/python"
    if not python.is_file():
        raise RuntimeError("Bulletproof Python environment is unavailable.")
    args.output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    outcomes = []
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers=headers,
        timeout=30,
    ) as api:
        existing_manifests = {
            item["manifest_key"]: item
            for item in api.get("/v1/research/data-contracts/manifests")
            .raise_for_status()
            .json()
        }
        existing_builds = {
            item["build_key"]: item
            for item in api.get("/v1/research/data-contracts/builds")
            .raise_for_status()
            .json()
        }
        for instrument in ("BTCUSDT", "ETHUSDT"):
            source = (
                args.bulletproof_root
                / f"research_data/canonical/binance/{instrument}/timeframe=1m/ohlcv.parquet"
            )
            first_path = args.output_root / f"{instrument.lower()}-1h-2025.csv"
            second_path = args.output_root / f".{instrument.lower()}-rebuild.csv"
            first, started, ended = build(python, source, first_path, instrument)
            second, _, _ = build(python, source, second_path, instrument)
            if first["content_digest"] != second["content_digest"]:
                raise RuntimeError(f"{instrument} did not rebuild bit-for-bit.")
            contract = manifest(instrument, first, source, args.as_of)
            manifest_digest = digest(contract)
            manifest_key = f"M15-{instrument}-1H-2025"
            manifest_record = existing_manifests.get(manifest_key)
            if manifest_record is not None:
                if manifest_record["manifest_digest"] != manifest_digest:
                    raise RuntimeError(f"Existing {instrument} manifest differs.")
            else:
                manifest_record = post(
                    api,
                    "/v1/research/data-contracts/manifests",
                    {
                        "manifest_key": manifest_key,
                        "manifest": contract,
                        "manifest_digest": manifest_digest,
                        "registered_by": "m15-data-registry",
                    },
                )
            build_document = {
                "build_key": f"M15-{instrument}-1H-2025-BUILD-1",
                "manifest_id": manifest_record["id"],
                "builder_repository": "swarm-control-plane",
                "builder_commit": args.source_commit,
                "builder_runtime": (
                    f"python-{platform.python_version()}-bulletproof-pandas-builder"
                ),
                "output_uri": f"m15://{first_path.name}",
                "rows": first["rows"],
                "started_at": started.isoformat(),
                "ended_at": ended.isoformat(),
                "content_digest": first["content_digest"],
                "rebuild_content_digest": second["content_digest"],
                "quality_results": [
                    {
                        "check": name,
                        "observed": value,
                        "maximum": 0,
                        "passed": value == 0,
                    }
                    for name, value in sorted(first["quality"].items())
                ],
            }
            build_record = existing_builds.get(build_document["build_key"])
            if build_record is not None:
                if (
                    build_record["content_digest"] != first["content_digest"]
                    or build_record["manifest_id"] != manifest_record["id"]
                ):
                    raise RuntimeError(f"Existing {instrument} build differs.")
            else:
                build_record = post(
                    api,
                    "/v1/research/data-contracts/builds",
                    build_document
                    | {
                        "record_digest": digest(build_document),
                        "built_by": "m15-data-builder",
                    },
                )
            outcomes.append(
                {
                    "instrument": instrument,
                    "manifest_id": manifest_record["id"],
                    "manifest_digest": manifest_digest,
                    "build_id": build_record["id"],
                    "content_digest": first["content_digest"],
                    "rebuild_content_digest": second["content_digest"],
                    "rows": first["rows"],
                    "quality": first["quality"],
                }
            )
    print(json.dumps({"datasets": outcomes, "success": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
