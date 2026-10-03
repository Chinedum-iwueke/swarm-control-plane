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


def parse_catalog_timestamp(value: object) -> datetime:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("catalog timestamps must include a timezone")
        return parsed.astimezone(UTC)
    raise ValueError("catalog timestamp is not an ISO-8601 string or Unix epoch")


def recent_catalog_window(
    catalog: dict, *, venues: set[str]
) -> tuple[datetime, datetime]:
    complete_ends = []
    for item in catalog.get("one_year_coverage_candidates", []):
        if (
            item.get("venue") not in venues
            or item.get("timeframe") != "1m"
            or item.get("fetch_status") != "success"
            or int(item.get("missing_rows") or 0) != 0
            or not item.get("last_ts")
        ):
            continue
        complete_ends.append(
            parse_catalog_timestamp(item["last_ts"]) + timedelta(minutes=1)
        )
    if not complete_ends:
        raise RuntimeError(
            "The DATA-002 catalog has no timestamped, gap-free one-year panel for "
            "the requested venues; no mandate was written."
        )
    window_end = max(complete_ends).replace(second=0, microsecond=0)
    return window_end - timedelta(days=365), window_end


def repository_head(repository: str) -> str:
    return subprocess.run(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def eligible_catalog_instruments(catalog: dict, *, venues: set[str]) -> list[str]:
    instruments = {
        str(item["instrument"]).upper()
        for item in catalog.get("one_year_coverage_candidates", [])
        if item.get("venue") in venues
        and item.get("instrument")
        and item.get("timeframe") == "1m"
        and item.get("fetch_status") == "success"
        and int(item.get("missing_rows") or 0) == 0
        and item.get("first_ts")
        and item.get("last_ts")
    }
    if not instruments:
        raise RuntimeError(
            "The DATA-002 catalog has no gap-free one-year instruments for the "
            "requested venues; no mandate was written."
        )
    return sorted(instruments)


def compatible_campaign_bindings(
    campaigns: list[dict],
    *,
    source_commit: str,
    source_campaign_id: str | None = None,
) -> list[dict]:
    """Return the deterministic admitted panel union for one native engine commit."""
    compatible = []
    for campaign in campaigns:
        specification = campaign.get("specification", {})
        if specification.get("bulletproof_source_commit") != source_commit:
            continue
        if source_campaign_id and campaign.get("id") != source_campaign_id:
            continue
        for item in specification.get("dataset_bindings", []):
            binding = {key: value for key, value in item.items() if key in BINDING_KEYS}
            if set(binding) != BINDING_KEYS:
                continue
            compatible.append(binding)
    unique: dict[str, dict] = {}
    for binding in compatible:
        identity = json.dumps(binding, sort_keys=True, separators=(",", ":"))
        unique.setdefault(identity, binding)
    bindings = [unique[key] for key in sorted(unique)]
    if not bindings:
        raise RuntimeError(
            "No complete admitted real-data bindings match the pinned native engine "
            "commit; no mandate was written."
        )
    return bindings


def binding_for_explicit_admission(
    specification: dict, admission: dict, receipt_id: UUID
) -> list[dict]:
    candidates = [
        {key: value for key, value in item.items() if key in BINDING_KEYS}
        for item in specification.get("dataset_bindings", [])
        if admission["dataset_digest"] in item.get("partition_digests", [])
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "An explicit producer receipt must match exactly one immutable "
            "source-campaign partition."
        )
    candidates[0]["producer_receipt_id"] = str(receipt_id)
    return candidates


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
    parser.add_argument("--maximum-assets-per-hypothesis", type=int, default=100)
    parser.add_argument("--question-queue-low-watermark", type=int, default=12)
    parser.add_argument("--maximum-parallel-campaigns", type=int, default=3)
    parser.add_argument(
        "--mandate-kind",
        choices=("canonical_weekly", "thematic"),
        default="canonical_weekly",
    )
    parser.add_argument("--parent-mandate-digest")
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
        if end - start != timedelta(days=365):
            parser.error(
                "The primary continuous research window must span exactly 365 days."
            )
    if not 1 <= args.maximum_assets_per_hypothesis <= 128:
        parser.error("--maximum-assets-per-hypothesis must be between 1 and 128.")
    if not 2 <= args.question_queue_low_watermark <= 100:
        parser.error("--question-queue-low-watermark must be between 2 and 100.")
    if not 1 <= args.maximum_parallel_campaigns <= 8:
        parser.error("--maximum-parallel-campaigns must be between 1 and 8.")
    if args.mandate_kind == "thematic" and not args.parent_mandate_digest:
        parser.error("Thematic mandates require --parent-mandate-digest.")
    if args.mandate_kind == "canonical_weekly" and args.parent_mandate_digest:
        parser.error("Canonical mandates cannot declare --parent-mandate-digest.")
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
        source_commit = (
            args.bulletproof_source_commit or specification["bulletproof_source_commit"]
        )
        if args.producer_receipt_id:
            receipt_response = client.get(
                f"/v1/research/quantitative-receipts/{args.producer_receipt_id}"
            )
            receipt_response.raise_for_status()
            explicit_admission = receipt_response.json()
            bindings = binding_for_explicit_admission(
                specification, explicit_admission, args.producer_receipt_id
            )
        else:
            bindings = compatible_campaign_bindings(
                campaigns,
                source_commit=source_commit,
                source_campaign_id=args.source_campaign_id,
            )
        checked_out_commit = repository_head(args.bulletproof_repository)
        if checked_out_commit != source_commit:
            raise RuntimeError(
                "The Bulletproof checkout does not match the exact requested source "
                "commit; no strategy catalog or mandate was written."
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
            result = admission["receipt"]["result"]
            if admission["dataset_digest"] not in binding["partition_digests"]:
                raise RuntimeError(
                    "Native admission does not bind a partition in the immutable "
                    "dataset binding; no mandate was written."
                )
            if not result.get("output_columns"):
                raise RuntimeError(
                    "Native admission omits its output-column contract; no mandate "
                    "was written."
                )
            binding["producer_receipt_id"] = admission["id"]
            binding["evidence_class"] = result["evidence_class"]
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
        if args.window_end:
            window_end = datetime.fromisoformat(args.window_end.replace("Z", "+00:00"))
            window_start = datetime.fromisoformat(
                args.window_start.replace("Z", "+00:00")
            )
        else:
            window_start, window_end = recent_catalog_window(
                catalog, venues=set(args.discovery_venues)
            )
        allowed_instruments = eligible_catalog_instruments(
            catalog, venues=set(args.discovery_venues)
        )
        payload = {
            "mandate_key": args.mandate_key or f"ALPHA004-WEEK-{moment:%Y%m%d}",
            "version": args.version,
            "objective": args.objective,
            "valid_from": moment.isoformat(),
            "valid_until": (moment + timedelta(days=7)).isoformat(),
            "bulletproof_source_commit": source_commit,
            "execution_window_start": window_start.isoformat(),
            "execution_window_end": window_end.isoformat(),
            "historical_window_policy": {
                "primary_policy": "latest_complete_utc_year",
                "primary_duration_days": 365,
                "deep_validation_max_days": 1095,
                "deep_validation_requires": [
                    "primary_window_survivor",
                    "independent_review_complete",
                    "explicit_followup_contract",
                ],
            },
            "mandate_kind": args.mandate_kind,
            "parent_mandate_digest": args.parent_mandate_digest,
            "dataset_bindings": bindings,
            "discovery_catalog": {
                "producer_receipt_id": catalog["receipt_id"],
                "receipt_digest": catalog["receipt_digest"],
                "source_commit": catalog["source_commit"],
                "allowed_venues": sorted(set(args.discovery_venues)),
                "selection_policy": "point_in_time_pre_outcome",
                "maximum_assets_per_hypothesis": args.maximum_assets_per_hypothesis,
                "large_basket_threshold": 20,
                "large_basket_policy": (
                    "point_in_time_overlap_liquidity_and_compute_admission"
                ),
            },
            "strategy_catalog": strategy_catalog,
            "allowed_venues": sorted(set(args.discovery_venues)),
            "allowed_instruments": allowed_instruments,
            "minimum_liquidity_usd": args.minimum_liquidity_usd,
            "budget": {
                "maximum_cycles": 42,
                "maximum_hypotheses": 100,
                "maximum_total_trials": 500,
                "maximum_variants_per_hypothesis": 8,
                "maximum_candidates_per_cycle": 5,
                "cadence_seconds": 3600,
                "maximum_consecutive_failures": 5,
                "question_queue_low_watermark": args.question_queue_low_watermark,
                "maximum_parallel_campaigns": args.maximum_parallel_campaigns,
            },
            "created_by": "founder-operator",
        }
        created = client.post("/v1/research/alpha-discovery/mandates", json=payload)
        if created.is_error:
            raise RuntimeError(
                f"Mandate registration failed ({created.status_code}): {created.text}"
            )
        print(json.dumps(created.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
