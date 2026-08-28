#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/risk002/report.json"),
    )
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=60.0) as client:
        snapshots = (
            client.get("/research/reference-data/snapshots").raise_for_status().json()
        )
        reference = next(
            item
            for item in snapshots
            if item["snapshot_key"] == "DATA001-BINANCE-BTC-FIXTURE-R1"
        )
        assessments = (
            client.get("/research/risk-stress-assessments").raise_for_status().json()
        )
        stress = next(
            item
            for item in assessments
            if item["assessment_key"] == "RISK001-LIVE-PILOT"
        )
        pack = {
            "schema_version": "venue-risk-rule-pack-v1.0.0",
            "venue_id": "binance",
            "instrument_id": "crypto:btc-usdt-perpetual",
            "listing_id": "binance:btc-perpetual",
            "version": "v1.0.0",
            "source_uri": "https://www.binance.com/en/support/faq/futures-rules",
            "source_digest": digest({"source": "risk002-live-fixture"}),
            "observed_at": "2026-08-28T10:00:00Z",
            "available_at": "2026-08-28T10:05:00Z",
            "effective_from": "2026-08-28T10:10:00Z",
            "effective_to": None,
            "status": "active",
            "transition": "activate",
            "supersedes_rule_pack_digest": None,
            "margin_tiers": [
                {
                    "tier": 1,
                    "notional_floor": "0",
                    "notional_cap": "100000",
                    "maximum_leverage": "10",
                    "maintenance_margin_rate": "0.005",
                    "maintenance_amount": "0",
                },
                {
                    "tier": 2,
                    "notional_floor": "100000",
                    "notional_cap": "500000",
                    "maximum_leverage": "5",
                    "maintenance_margin_rate": "0.01",
                    "maintenance_amount": "500",
                },
            ],
            "price_increment": "0.1",
            "quantity_increment": "0.001",
            "maximum_mark_deviation": "0.02",
            "maximum_abs_funding_rate": "0.001",
            "minimum_liquidation_buffer": "100",
        }
        request = {
            "schema_version": "risk-rule-evaluation-request-v1.0.0",
            "reference_snapshot_id": reference["id"],
            "reference_snapshot_digest": reference["snapshot_digest"],
            "risk_stress_assessment_id": stress["id"],
            "risk_stress_dossier_digest": stress["dossier_digest"],
            "rule_pack": pack,
            "rule_pack_digest": digest(pack),
            "position": {
                "side": "long",
                "quantity": "1.000",
                "entry_price": "50000.0",
                "mark_price": "50500.0",
                "index_price": "50400.0",
                "collateral": "10000.0",
                "requested_leverage": "5.0",
                "accrued_funding": "10.0",
                "fee_reserve": "25.0",
                "state_digest": digest({"position": "risk002-live"}),
            },
            "evaluated_at": "2026-08-28T12:00:00Z",
            "maximum_rule_age_seconds": 7200,
            "allocation_authority": False,
            "order_authority": False,
            "capital_authority": False,
        }
        payload = {
            "evaluation_key": "RISK002-LIVE-PILOT",
            "request": request,
            "request_digest": digest(request),
            "evaluated_by": "risk002-pilot",
        }
        evaluation = (
            client.post("/research/risk-rule-evaluations", json=payload)
            .raise_for_status()
            .json()
        )
        replay = (
            client.get(f"/research/risk-rule-evaluations/{evaluation['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "risk002-pilot-report-v1.0.0",
        "success": evaluation["decision"] == "allowed" and replay == evaluation,
        "evaluation_id": evaluation["id"],
        "receipt_digest": evaluation["receipt_digest"],
        "decision": evaluation["decision"],
        "reference_snapshot_id": reference["id"],
        "risk_stress_assessment_id": stress["id"],
        "selected_margin_tier": evaluation["receipt"]["selected_margin_tier"],
        "liquidation_buffer": evaluation["receipt"]["liquidation_buffer"],
        "failures": evaluation["receipt"]["failures"],
        "exact_replay": replay == evaluation,
        "allocation_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
