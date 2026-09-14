#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta

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
    args = parser.parse_args()
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
        moment = datetime.now(UTC)
        payload = {
            "mandate_key": f"ALPHA004-WEEK-{moment:%Y%m%d}",
            "version": "1.0.0",
            "objective": args.objective,
            "valid_from": moment.isoformat(),
            "valid_until": (moment + timedelta(days=7)).isoformat(),
            "bulletproof_source_commit": specification["bulletproof_source_commit"],
            "execution_window_start": specification["execution_window_start"],
            "execution_window_end": specification["execution_window_end"],
            "dataset_bindings": bindings,
            "allowed_venues": specification["allowed_venues"],
            "allowed_instruments": specification["allowed_instruments"],
            "minimum_liquidity_usd": 0,
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
