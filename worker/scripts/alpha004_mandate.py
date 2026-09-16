#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

BINDING_KEYS = {
    "dataset_build_id",
    "catalog_id",
    "lake_governance_snapshot_id",
    "producer_receipt_id",
    "dataset_key",
    "partition_digests",
    "evidence_class",
    "research_principal",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--objective",
        default=(
            "Continuously discover and falsify predictive micro-alpha hypotheses from "
            "institutional evidence using admitted Binance and Bybit perpetual data."
        ),
    )
    parser.add_argument("--minimum-liquidity-usd", type=float, default=1_000_000)
    parser.add_argument("--mandate-key")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--source-campaign-id")
    parser.add_argument("--bulletproof-source-commit")
    parser.add_argument(
        "--bulletproof-repository",
        default="/home/omenka/Projects/bulletproof_bt",
    )
    parser.add_argument(
        "--bulletproof-python",
        default="/home/omenka/Projects/bulletproof_bt/.venv/bin/python",
    )
    parser.add_argument("--producer-receipt-id", type=UUID)
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument(
        "--discovery-venues",
        nargs="+",
        choices=("binance", "bybit"),
        default=["binance", "bybit"],
        help=(
            "Founder-approved manifest visibility for pre-outcome hypothesis design; "
            "selected panels still require content admission before execution."
        ),
    )
    args = parser.parse_args()
    if bool(args.window_start) != bool(args.window_end):
        parser.error("Supply both --window-start and --window-end.")
    if args.window_start:
        start = datetime.fromisoformat(args.window_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(args.window_end.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            parser.error(
                "Window timestamps require a timezone, for example 2025-05-01T00:00:00Z."
            )
        if end - start < timedelta(days=365):
            parser.error("The continuous research window must span at least 365 days.")
    if args.bulletproof_source_commit and not re.fullmatch(
        r"[0-9a-f]{40}", args.bulletproof_source_commit
    ):
        parser.error(
            "--bulletproof-source-commit requires the exact 40-character reviewed commit."
        )
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"), headers=headers, timeout=60
    ) as client:
        response = client.get("/v1/research/alpha-campaigns", params={"limit": 100})
        response.raise_for_status()
        campaigns = response.json()
        source = next(
            (
                item
                for item in campaigns
                if item.get("specification", {}).get("dataset_bindings")
                and item.get("specification", {}).get("execution_window_start")
                and (
                    not args.source_campaign_id or item["id"] == args.source_campaign_id
                )
            ),
            None,
        )
        if source is None:
            raise RuntimeError("No admitted real-data campaign can seed the mandate.")
        specification = source["specification"]
        bindings = [
            {key: value for key, value in item.items() if key in BINDING_KEYS}
            for item in specification["dataset_bindings"]
        ]
        if args.producer_receipt_id:
            if len(bindings) != 1:
                raise RuntimeError(
                    "An explicit producer receipt requires exactly one dataset binding."
                )
            bindings[0]["producer_receipt_id"] = str(args.producer_receipt_id)
        source_commit = (
            args.bulletproof_source_commit or specification["bulletproof_source_commit"]
        )
        strategy_catalog = json.loads(
            subprocess.run(
                [
                    args.bulletproof_python,
                    f"{args.bulletproof_repository}/scripts/build_alpha_strategy_catalog.py",
                    "--repository",
                    args.bulletproof_repository,
                    "--source-commit",
                    source_commit,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        for binding in bindings:
            receipt_response = client.get(
                f"/v1/research/quantitative-receipts/{binding['producer_receipt_id']}"
            )
            receipt_response.raise_for_status()
            admission = receipt_response.json()
            if admission["source_commit"] != source_commit:
                raise RuntimeError(
                    "Real-data admission is bound to another engine commit. Rebuild/register the native ALPHA-001 admission receipt and supply --producer-receipt-id; no mandate was written."
                )
        catalog_response = client.get(
            "/v1/research/quantitative-receipts/lake-inventory"
        )
        catalog_response.raise_for_status()
        catalog = catalog_response.json()
        if (
            catalog.get("status") != "manifest_catalog_visible_unadmitted"
            or not catalog.get("receipt_id")
            or not catalog.get("receipt_digest")
            or not catalog.get("source_commit")
            or not set(args.discovery_venues).issubset(
                set(catalog.get("venue_scope", []))
            )
            or catalog.get("execution_authority") is not False
        ):
            raise RuntimeError(
                "No immutable no-authority manifest catalog covers the requested discovery venues."
            )
        moment = datetime.now(UTC)
        payload = {
            "mandate_key": args.mandate_key or f"ALPHA004-WEEK-{moment:%Y%m%d}",
            "version": args.version,
            "objective": args.objective,
            "valid_from": moment.isoformat(),
            "valid_until": (moment + timedelta(days=7)).isoformat(),
            "bulletproof_source_commit": source_commit,
            "execution_window_start": args.window_start
            or specification["execution_window_start"],
            "execution_window_end": args.window_end
            or specification["execution_window_end"],
            "dataset_bindings": bindings,
            "discovery_catalog": {
                "producer_receipt_id": catalog["receipt_id"],
                "receipt_digest": catalog["receipt_digest"],
                "source_commit": catalog["source_commit"],
                "allowed_venues": sorted(set(args.discovery_venues)),
                "selection_policy": "point_in_time_pre_outcome",
                "maximum_assets_per_hypothesis": 8,
            },
            "strategy_catalog": strategy_catalog,
            "allowed_venues": specification["allowed_venues"],
            "allowed_instruments": specification["allowed_instruments"],
            "minimum_liquidity_usd": args.minimum_liquidity_usd,
            "budget": {
                "maximum_cycles": 42,
                "maximum_hypotheses": 100,
                "maximum_total_trials": 500,
                "maximum_variants_per_hypothesis": 8,
                "maximum_candidates_per_cycle": 5,
                "cadence_seconds": 3600,
                "maximum_consecutive_failures": 5,
            },
            "created_by": "founder-operator",
        }
        created = client.post("/v1/research/alpha-discovery/mandates", json=payload)
        created.raise_for_status()
        print(json.dumps(created.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
