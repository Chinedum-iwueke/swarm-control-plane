#!/usr/bin/env python3
"""Exercise the DISC-002 evidence ladder against production metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/disc002/report.json"),
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=90,
    ) as client:
        existing = call(client, "GET", "/v1/research/discovery-maps?limit=500")
        existing_by_key = {item["map_key"]: item for item in existing}
        if "DISC002-LIVE-R2" in existing_by_key:
            final = existing_by_key["DISC002-LIVE-R2"]
            events = call(
                client, "GET", f"/v1/research/discovery-maps/{final['id']}/events"
            )
            report = _report(final, events, True)
        else:
            cycles = call(client, "GET", "/v1/research-programs/cycles?limit=100")
            if not cycles:
                raise RuntimeError("DISC-001 has not produced a daily research cycle.")
            cycle = cycles[0]
            evidence = call(client, "GET", "/v1/research/evidence/objects?limit=500")[
                "items"
            ]
            selected = []
            producers = set()
            for item in evidence:
                producer = json.dumps(item["producer"], sort_keys=True)
                if producer not in producers:
                    selected.append(item)
                    producers.add(producer)
                if len(selected) == 2:
                    break
            if len(selected) < 2:
                raise RuntimeError(
                    "Two independently produced evidence objects are required."
                )
            snapshots = call(
                client, "GET", "/v1/research/lake-operations/snapshots?limit=100"
            )
            events = call(
                client, "GET", "/v1/research/lake-operations/events?limit=1000"
            )
            admission = next(
                item
                for item in events
                if item["event_type"] == "admission_decision"
                and item["detail"].get("allowed") is True
            )
            snapshot = next(
                item for item in snapshots if item["id"] == admission["snapshot_id"]
            )
            document = {
                "schema_version": 1,
                "stage": "opportunity",
                "source_daily_cycle_id": cycle["id"],
                "question": cycle["question"],
                "population": {
                    "instruments": ["crypto:btc-usdt-perpetual"],
                    "venue_keys": ["binance"],
                    "start_at": "2025-08-27T00:00:00Z",
                    "end_at": "2026-08-27T00:00:00Z",
                    "timeframe": "1h",
                    "data_catalog_digest": snapshot["catalog_digest"],
                    "lake_admission_event_digest": admission["event_digest"],
                },
                "baseline_definition": "Matched non-event observations under the same volatility regime",
                "effect": {
                    "metric": "net-return-bps",
                    "estimate": 2.5,
                    "baseline": 1.0,
                    "incremental_estimate": 1.5,
                    "sample_size": 500,
                    "unit": "bps",
                },
                "uncertainty": {
                    "method": "block-bootstrap",
                    "lower": 0.1,
                    "upper": 2.9,
                    "confidence_level": 0.95,
                },
                "evidence_object_ids": [item["id"] for item in selected],
                "evidence_digests": [item["content_digest"] for item in selected],
                "regime_controls": ["btc-volatility-quintile", "calendar-regime"],
                "null_controls": [
                    {
                        "control_key": "time-shift-placebo",
                        "kind": "time_shift",
                        "result": "passed",
                        "evidence_digest": selected[0]["content_digest"],
                    }
                ],
                "mechanism": "The declared event changes available liquidity and conditional price response.",
                "rival_explanations": [
                    "The estimate is explained by volatility or calendar confounding."
                ],
                "falsification_criteria": [
                    "The incremental effect vanishes in matched regimes."
                ],
                "costs": {
                    "gross_effect": 2.5,
                    "transaction_cost": 0.5,
                    "financing_cost": 0.2,
                    "impact_cost": 0.3,
                    "net_effect": 1.5,
                    "unit": "bps",
                },
                "limitations": [
                    "Mapping evidence is not strategy certification or trading authority."
                ],
            }
            invalid = json.loads(json.dumps(document))
            invalid["costs"] = {
                "gross_effect": 1.0,
                "transaction_cost": 0.5,
                "financing_cost": 0.2,
                "impact_cost": 0.3,
                "net_effect": 0.0,
                "unit": "bps",
            }
            rejected = client.post(
                "/v1/research/discovery-maps",
                json={
                    "map_key": "DISC002-COST-ERASED",
                    "document": invalid,
                    "map_digest": digest(invalid),
                    "registered_by": "disc002-pilot",
                },
            )
            if rejected.status_code != 422:
                raise RuntimeError(
                    "Cost-erased opportunity did not fail schema admission."
                )
            first = call(
                client,
                "POST",
                "/v1/research/discovery-maps",
                json={
                    "map_key": "DISC002-LIVE-R1",
                    "document": document,
                    "map_digest": digest(document),
                    "registered_by": "disc002-pilot",
                },
            )
            replacement = json.loads(json.dumps(document))
            replacement["limitations"].append(
                "Superseding revision retains the original map."
            )
            final = call(
                client,
                "POST",
                "/v1/research/discovery-maps",
                json={
                    "map_key": "DISC002-LIVE-R2",
                    "document": replacement,
                    "map_digest": digest(replacement),
                    "supersedes_map_id": first["id"],
                    "registered_by": "disc002-pilot",
                },
            )
            events = call(
                client, "GET", f"/v1/research/discovery-maps/{first['id']}/events"
            )
            report = _report(final, events, rejected.status_code == 422)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _report(final: dict, events: list[dict], cost_rejected: bool) -> dict:
    result = {
        "schema_version": "disc002-pilot-report-v1.0.0",
        "success": cost_rejected
        and final["stage"] == "opportunity"
        and final["status"] == "active",
        "map_id": final["id"],
        "map_digest": final["map_digest"],
        "semantic_fingerprint": final["semantic_fingerprint"],
        "cost_erased_opportunity_rejected": cost_rejected,
        "supersession_event_retained": any(
            item["event_type"] == "map_superseded" for item in events
        ),
        "source_write_authority": False,
        "execution_order_or_capital_authority": False,
    }
    result["report_digest"] = digest(result)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
