#!/usr/bin/env python3
"""Register and exactly replay an authoritative Bulletproof EXEC-005 receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = json.loads(args.native_report.read_text(encoding="utf-8"))
    receipt = native["receipt"]
    if not native.get("success") or receipt.get("milestone") != "EXEC-005":
        raise RuntimeError(
            "native report is not a successful EXEC-005 producer report"
        )
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    schema_payload = {
        "name": "execution-quality-calibration",
        "version": "1.0.0",
        "producer": "bt.institutional.execution_calibration.execution_calibration_receipt",
        "source_commit": receipt["source_commit"],
        "specification_digest": native["calibration_specification_digest"],
        "specification": native["calibration_specification"],
        "status": "active",
        "registered_by": "exec005-pilot",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        schema_response = client.post(
            "/v1/research/execution-calibration-schemas", json=schema_payload
        )
        schema_response.raise_for_status()
        schema = schema_response.json()
        schema_replay = client.get(
            f"/v1/research/execution-calibration-schemas/{schema['id']}"
        )
        schema_replay.raise_for_status()
        receipt_response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "exec005-pilot"},
        )
        receipt_response.raise_for_status()
        registered = receipt_response.json()
        receipt_replay = client.get(
            f"/v1/research/quantitative-receipts/{registered['id']}"
        )
        receipt_replay.raise_for_status()
    calibration = receipt["result"]["calibration"]
    exact = (
        schema_replay.json()["specification_digest"]
        == native["calibration_specification_digest"]
        and receipt_replay.json()["receipt_digest"] == receipt["receipt_digest"]
    )
    success = (
        exact
        and calibration["qualified"]
        and native["sparse_evidence"]["decision"] == "use_pessimistic_fallback"
        and not any(receipt["authority"].values())
    )
    result = {
        "schema_version": "exec005-cross-repository-pilot-v1.0.0",
        "success": success,
        "execution_calibration_schema_id": schema["id"],
        "execution_calibration_schema_digest": schema["specification_digest"],
        "quantitative_receipt_id": registered["id"],
        "receipt_digest": registered["receipt_digest"],
        "calibration_digest": calibration["calibration_digest"],
        "empirical_bundle_digest": receipt["result"][
            "empirical_market_model_bundle"
        ]["bundle_digest"],
        "strata": len(calibration["strata"]),
        "future_observations_excluded": calibration["future_observations_excluded"],
        "sparse_evidence_decision": native["sparse_evidence"]["decision"],
        "capital_or_order_authority": False,
    }
    result["report_digest"] = digest(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
