#!/usr/bin/env python3
"""Register and exactly replay an authoritative Bulletproof EXEC-011 bundle."""

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
    if not native.get("success") or receipt.get("milestone") != "EXEC-011":
        raise RuntimeError("native report is not a successful EXEC-011 producer report")
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    result = receipt["result"]
    schema_payload = {
        "name": "canonical-venue-telemetry",
        "version": "1.0.0",
        "producer": "bt.institutional.venue_telemetry.venue_telemetry_receipt",
        "source_commit": receipt["source_commit"],
        "specification_digest": native["telemetry_specification_digest"],
        "specification": native["telemetry_specification"],
        "status": "active",
        "registered_by": "exec011-pilot",
    }
    replay_payload = {
        "receipt_digest": receipt["receipt_digest"],
        "projection_digest": result["projection_digest"],
        "schema_digest": result["telemetry_schema_digest"],
        "venue": result["venue"],
        "environment": result["environment"],
        "account_pseudonym": result["account_pseudonym"],
        "observed_at": result["projection"]["known_at"],
        "status": result["projection"]["status"],
        "projection": result["projection"],
        "registered_by": "exec011-pilot",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        schema_response = client.post(
            "/v1/execution/telemetry-schemas", json=schema_payload
        )
        schema_response.raise_for_status()
        schema = schema_response.json()
        receipt_response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "exec011-pilot"},
        )
        receipt_response.raise_for_status()
        registered = receipt_response.json()
        replay_response = client.post("/v1/execution/replays", json=replay_payload)
        replay_response.raise_for_status()
        replay = replay_response.json()
        exact = client.get(f"/v1/execution/replays/{replay['id']}")
        exact.raise_for_status()
        overview = client.get(
            "/v1/execution/overview", params={"environment": result["environment"]}
        )
        overview.raise_for_status()
    exact_replay = exact.json()["projection_digest"] == result["projection_digest"]
    visible = any(
        item["receipt_digest"] == receipt["receipt_digest"]
        for item in overview.json()["venues"]
    )
    report = {
        "schema_version": "exec011-cross-repository-pilot-v1.0.0",
        "success": exact_replay and visible and result["reconstructable"],
        "execution_telemetry_schema_id": schema["id"],
        "execution_telemetry_schema_digest": schema["specification_digest"],
        "quantitative_receipt_id": registered["id"],
        "receipt_digest": registered["receipt_digest"],
        "replay_id": replay["id"],
        "projection_digest": replay["projection_digest"],
        "environment": replay["environment"],
        "venue": replay["venue"],
        "event_count": replay["projection"]["event_count"],
        "trade_episode_count": len(replay["projection"]["trade_episodes"]),
        "exact_replay": exact_replay,
        "mission_control_visible": visible,
        "capital_or_order_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
