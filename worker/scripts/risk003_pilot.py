#!/usr/bin/env python3
"""Register and exactly replay an authoritative Bulletproof RISK-003 receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = json.loads(args.native_report.read_text(encoding="utf-8"))
    receipt = native["receipt"]
    if not native.get("success") or receipt.get("milestone") != "RISK-003":
        raise RuntimeError("native report is not a successful RISK-003 producer report")
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    schema_payload = {
        "name": "dynamic-risk-budget-regime-scaling",
        "version": "1.0.0",
        "producer": "bt.institutional.risk_budget.dynamic_risk_budget_receipt",
        "source_commit": receipt["source_commit"],
        "specification_digest": native["risk_budget_specification_digest"],
        "specification": native["risk_budget_specification"],
        "status": "active",
        "registered_by": "risk003-pilot",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        schema_response = client.post("/v1/research/risk-budget-schemas", json=schema_payload)
        schema_response.raise_for_status()
        schema = schema_response.json()
        schema_replay = client.get(f"/v1/research/risk-budget-schemas/{schema['id']}")
        schema_replay.raise_for_status()
        receipt_response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "risk003-pilot"},
        )
        receipt_response.raise_for_status()
        registered = receipt_response.json()
        receipt_replay = client.get(f"/v1/research/quantitative-receipts/{registered['id']}")
        receipt_replay.raise_for_status()
    result = receipt["result"]
    exact = (
        schema_replay.json()["specification_digest"] == native["risk_budget_specification_digest"]
        and receipt_replay.json()["receipt_digest"] == receipt["receipt_digest"]
    )
    success = bool(
        exact
        and result["qualified"]
        and native["uncertainty_monotonic"]
        and native["stale_input"]["decision"] == "static_conservative_fallback"
        and not any(receipt["authority"].values())
    )
    report = {
        "schema_version": "risk003-cross-repository-pilot-v1.0.0",
        "success": success,
        "risk_budget_schema_id": schema["id"],
        "risk_budget_schema_digest": schema["specification_digest"],
        "quantitative_receipt_id": registered["id"],
        "receipt_digest": registered["receipt_digest"],
        "budget_digest": result["budget_digest"],
        "effective_risk_fraction": result["effective_risk_fraction"],
        "effective_risk_notional": result["effective_risk_notional"],
        "stale_input_decision": native["stale_input"]["decision"],
        "uncertainty_monotonic": native["uncertainty_monotonic"],
        "capital_or_order_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
