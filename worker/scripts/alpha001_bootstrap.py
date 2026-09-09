from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import httpx


def call(client: httpx.Client, method: str, path: str, payload: dict | None = None):
    response = client.request(method, path, json=payload)
    if response.is_error:
        raise RuntimeError(
            f"{method} {path} failed ({response.status_code}): {response.text}"
        )
    return response.json()


def select_bindings(
    client: httpx.Client, receipt: dict
) -> tuple[dict, dict, dict, dict, dict]:
    result = receipt["result"]
    dataset_digest = receipt["dataset_digest"]
    venue = result["venue"]
    instrument = result["instrument"]
    builds = call(client, "GET", "/v1/research/data-contracts/builds?limit=200")
    build = next(
        (item for item in builds if item["content_digest"] == dataset_digest), None
    )
    if build is None:
        raise RuntimeError(
            "No immutable DATA-002 build matches the Bulletproof panel digest."
        )
    catalogs = call(
        client, "GET", "/v1/research/market-data-catalog/snapshots?limit=200"
    )
    matches: list[tuple[dict, dict]] = []
    for catalog in catalogs:
        for partition in catalog["catalog"]["partitions"]:
            if (
                partition["content_digest"] == dataset_digest
                and partition["layer"] == "curated"
                and partition["venue_id"].lower() == venue
                and partition["instrument_id"].upper() == instrument
            ):
                matches.append((catalog, partition))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one immutable catalog partition for the panel; found {len(matches)}."
        )
    catalog, partition = matches[0]
    snapshots = call(client, "GET", "/v1/research/lake-operations/snapshots?limit=200")
    lake = next(
        (
            item
            for item in snapshots
            if item["catalog_digest"] == catalog["catalog_digest"]
            and any(
                rule["principal"] == "alpha-research-runner"
                and partition["dataset_key"] in rule["dataset_keys"]
                and "read" in rule["actions"]
                and rule["purpose"] == "research"
                for rule in item["snapshot"]["entitlements"]
            )
        ),
        None,
    )
    if lake is None:
        raise RuntimeError(
            "No DATA-003 snapshot grants the bounded alpha runner read access."
        )
    portfolios = call(client, "GET", "/v1/research/discovery-portfolios?limit=100")
    portfolio = next(
        (
            item
            for item in portfolios
            if item["project"] == "bulletproof-bt"
            and item["status"] == "allocated"
            and item["selected_count"] > 0
        ),
        None,
    )
    if portfolio is None:
        raise RuntimeError(
            "No allocated DISC-009 portfolio is available for bulletproof-bt."
        )
    return build, catalog, partition, lake, portfolio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register and optionally activate ALPHA-001."
    )
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--campaign-key", default="ALPHA001-REAL-DATA")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument(
        "--objective",
        default="Continuously produce bounded, reproducible answers from selected research questions on admitted real exchange history while retaining every negative, invalid, and failed result.",
    )
    parser.add_argument("--max-hypotheses", type=int, default=20)
    parser.add_argument("--max-total-trials", type=int, default=320)
    parser.add_argument("--max-variants", type=int, default=16)
    parser.add_argument("--max-duration-seconds", type=int, default=604800)
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if (
        receipt.get("milestone") != "ALPHA-001"
        or receipt.get("result", {}).get("admitted") is not True
    ):
        raise RuntimeError("Receipt is not an admitted ALPHA-001 real-data receipt.")
    api_url = os.environ["SWARM_API_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=60) as client:
        registered_receipt = call(
            client,
            "POST",
            "/v1/research/quantitative-receipts",
            {"receipt": receipt, "registered_by": "alpha-research-runner"},
        )
        build, catalog, partition, lake, portfolio = select_bindings(client, receipt)
        payload = {
            "campaign_key": args.campaign_key,
            "version": args.version,
            "project": "bulletproof-bt",
            "objective": args.objective,
            "discovery_portfolio_id": portfolio["id"],
            "dataset_bindings": [
                {
                    "dataset_build_id": build["id"],
                    "catalog_id": catalog["id"],
                    "lake_governance_snapshot_id": lake["id"],
                    "producer_receipt_id": registered_receipt["id"],
                    "dataset_key": partition["dataset_key"],
                    "partition_digests": [partition["content_digest"]],
                    "evidence_class": "live_exchange_history",
                    "research_principal": "alpha-research-runner",
                }
            ],
            "bulletproof_source_commit": receipt["source_commit"],
            "allowed_venues": [receipt["result"]["venue"]],
            "allowed_instruments": [receipt["result"]["instrument"]],
            "budget": {
                "max_hypotheses": args.max_hypotheses,
                "max_total_trials": args.max_total_trials,
                "max_variants_per_hypothesis": args.max_variants,
                "max_duration_seconds": args.max_duration_seconds,
                "max_consecutive_failures": args.max_consecutive_failures,
            },
            "created_by": "founder-operator",
        }
        campaign = call(client, "POST", "/v1/research/alpha-campaigns", payload)
        if args.activate and campaign["status"] == "awaiting_activation":
            campaign = call(
                client,
                "POST",
                f"/v1/research/alpha-campaigns/{campaign['id']}/activate",
                {
                    "expected_campaign_digest": campaign["campaign_digest"],
                    "actor": "founder-operator",
                    "reason": "Activate the bounded no-capital real-data research campaign.",
                },
            )
    state = {
        "campaign_id": campaign["id"],
        "campaign_digest": campaign["campaign_digest"],
        "status": campaign["status"],
        "dataset_digest": receipt["dataset_digest"],
        "producer_receipt_id": registered_receipt["id"],
        "producer_receipt_digest": registered_receipt["receipt_digest"],
        "discovery_portfolio_id": portfolio["id"],
        "capital_authority": False,
        "order_authority": False,
    }
    args.state.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.state.parent, delete=False
    ) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    temporary.replace(args.state)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
