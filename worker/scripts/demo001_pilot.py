#!/usr/bin/env python3
"""Register and exactly replay an authoritative Bulletproof DEMO-001 receipt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = json.loads(args.native_report.read_text(encoding="utf-8"))
    receipt = native.get("producer_receipt", {})
    if receipt.get("milestone") != "DEMO-001":
        raise RuntimeError("native report does not contain a DEMO-001 receipt")
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    schema_payload = {
        "name": "production-like-venue-demo-certification",
        "version": "1.0.0",
        "producer": "bt.institutional.demo_certification.demo_certification_receipt",
        "source_commit": receipt["source_commit"],
        "specification_digest": native["demo_certification_specification_digest"],
        "specification": native["demo_certification_specification"],
        "status": "active",
        "registered_by": "demo001-pilot",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        schema_response = client.post("/v1/research/demo-certification-schemas", json=schema_payload)
        schema_response.raise_for_status()
        schema = schema_response.json()
        registered_response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "demo001-pilot"},
        )
        registered_response.raise_for_status()
        registered = registered_response.json()
        replay = client.get(f"/v1/research/quantitative-receipts/{registered['id']}")
        replay.raise_for_status()
    exact = replay.json()["receipt_digest"] == receipt["receipt_digest"]
    report = {
        "schema_version": "demo001-cross-repository-pilot-v1.0.0",
        "success": bool(native.get("success") and exact),
        "demo_certification_schema_id": schema["id"],
        "demo_certification_schema_digest": schema["specification_digest"],
        "quantitative_receipt_id": registered["id"],
        "receipt_digest": receipt["receipt_digest"],
        "status": receipt["result"]["status"],
        "qualified": receipt["result"]["qualified"],
        "micro_live_eligible": False,
        "capital_or_live_order_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
