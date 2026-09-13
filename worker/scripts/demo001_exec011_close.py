#!/usr/bin/env python3
"""Export exact dependencies or publish the DEMO-001/EXEC-011 closure bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx

PRODUCERS = {
    "EXEC-001": "bt.institutional.execution.execution_journal_receipt",
    "EXEC-002": "bt.institutional.microstructure.microstructure_state_receipt",
    "EXEC-003": "bt.institutional.venue.venue_identity_receipt",
    "EXEC-004": "bt.institutional.oms.oms_reconciliation_receipt",
    "EXEC-005": "bt.institutional.execution_calibration.execution_calibration_receipt",
    "EXEC-006": "bt.institutional.execution_scheduler.execution_schedule_receipt",
    "EXEC-007": "bt.institutional.runtime_safety.runtime_safety_receipt",
    "EXEC-008": "bt.institutional.adapter_certification.adapter_certification_receipt",
    "EXEC-009": "bt.institutional.execution_degradation.execution_degradation_receipt",
    "RISK-005": "bt.institutional.realtime_risk.realtime_risk_decision_receipt",
    "SHADOW-002": "bt.institutional.shadow_monitoring.shadow_monitoring_receipt",
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def client() -> httpx.Client:
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    return httpx.Client(base_url=base, headers=headers, timeout=60)


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    path.chmod(0o600)


def export_dependencies(output: Path) -> int:
    selected: dict[str, dict[str, Any]] = {}
    with client() as api:
        response = api.get("/v1/research/quantitative-receipts")
        response.raise_for_status()
        for record in response.json():
            milestone = record.get("milestone")
            if milestone in selected or PRODUCERS.get(milestone) != record.get("producer"):
                continue
            selected[milestone] = record["receipt"]
    missing = sorted(set(PRODUCERS) - set(selected))
    if missing:
        raise RuntimeError(f"production receipt inventory is incomplete: {', '.join(missing)}")
    write(output, selected)
    print(json.dumps({
        "success": True,
        "dependencies": {
            key: {
                "receipt_digest": value["receipt_digest"],
                "dataset_digest": value["dataset_digest"],
            }
            for key, value in sorted(selected.items())
        },
    }, indent=2, sort_keys=True))
    return 0


def register_schema(api: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = api.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def register_receipt(api: httpx.Client, receipt: dict[str, Any]) -> dict[str, Any]:
    response = api.post(
        "/v1/research/quantitative-receipts",
        json={"receipt": receipt, "registered_by": "demo001-exec011-closure"},
    )
    response.raise_for_status()
    record = response.json()
    replay = api.get(f"/v1/research/quantitative-receipts/{record['id']}")
    replay.raise_for_status()
    if replay.json()["receipt_digest"] != receipt["receipt_digest"]:
        raise RuntimeError(f"{receipt['milestone']} receipt replay was not exact")
    return record


def publish(native_report: Path, output: Path) -> int:
    native = json.loads(native_report.read_text(encoding="utf-8"))
    if native.get("success") is not True:
        raise RuntimeError("native closure report is not successful")
    receipts = native["receipts"]
    if set(receipts) != {"EXEC-008", "EXEC-011", "DEMO-001"}:
        raise RuntimeError("native closure receipt set is incomplete")
    with client() as api:
        adapter_schema = register_schema(api, "/v1/research/adapter-certification-schemas", {
            "name": "venue-adapter-certification-and-demo-parity",
            "version": "1.1.0",
            "producer": receipts["EXEC-008"]["producer"],
            "source_commit": receipts["EXEC-008"]["source_commit"],
            "specification_digest": native["adapter_specification_digest"],
            "specification": native["adapter_specification"],
            "status": "active",
            "registered_by": "demo001-exec011-closure",
        })
        telemetry_schema = register_schema(api, "/v1/execution/telemetry-schemas", {
            "name": "canonical-venue-telemetry",
            "version": "1.0.0",
            "producer": receipts["EXEC-011"]["producer"],
            "source_commit": receipts["EXEC-011"]["source_commit"],
            "specification_digest": native["telemetry_specification_digest"],
            "specification": native["telemetry_specification"],
            "status": "active",
            "registered_by": "demo001-exec011-closure",
        })
        demo_schema = register_schema(api, "/v1/research/demo-certification-schemas", {
            "name": "production-like-venue-demo-certification",
            "version": "1.1.0",
            "producer": receipts["DEMO-001"]["producer"],
            "source_commit": receipts["DEMO-001"]["source_commit"],
            "specification_digest": native["demo_specification_digest"],
            "specification": native["demo_specification"],
            "status": "active",
            "registered_by": "demo001-exec011-closure",
        })
        registered = {
            milestone: register_receipt(api, receipts[milestone])
            for milestone in ("EXEC-008", "EXEC-011", "DEMO-001")
        }
        telemetry = receipts["EXEC-011"]["result"]
        projection = telemetry["projection"]
        replay_response = api.post("/v1/execution/replays", json={
            "receipt_digest": receipts["EXEC-011"]["receipt_digest"],
            "projection_digest": telemetry["projection_digest"],
            "schema_digest": telemetry["telemetry_schema_digest"],
            "venue": telemetry["venue"],
            "environment": telemetry["environment"],
            "account_pseudonym": telemetry["account_pseudonym"],
            "observed_at": projection["known_at"],
            "status": projection["status"],
            "projection": projection,
            "registered_by": "demo001-exec011-closure",
        })
        replay_response.raise_for_status()
        replay = replay_response.json()
        exact = api.get(f"/v1/execution/replays/{replay['id']}")
        exact.raise_for_status()
        overview = api.get("/v1/execution/overview", params={"environment": "demo"})
        overview.raise_for_status()
    mission_control_visible = any(
        item["receipt_digest"] == receipts["EXEC-011"]["receipt_digest"]
        for item in overview.json()["venues"]
    )
    success = bool(
        exact.json()["projection_digest"] == telemetry["projection_digest"]
        and mission_control_visible
        and telemetry["reconstructable"]
        and receipts["DEMO-001"]["result"]["qualified"]
    )
    report = {
        "schema_version": "demo001-exec011-publication-v1.0.0",
        "success": success,
        "schemas": {
            "EXEC-008": adapter_schema["specification_digest"],
            "EXEC-011": telemetry_schema["specification_digest"],
            "DEMO-001": demo_schema["specification_digest"],
        },
        "receipts": {
            key: {"id": value["id"], "receipt_digest": value["receipt_digest"]}
            for key, value in registered.items()
        },
        "replay_id": replay["id"],
        "projection_digest": replay["projection_digest"],
        "event_count": projection["event_count"],
        "trade_episode_count": len(projection["trade_episodes"]),
        "mission_control_visible": mission_control_visible,
        "demo_qualified": receipts["DEMO-001"]["result"]["qualified"],
        "live_or_capital_authority": False,
    }
    report["report_digest"] = digest(report)
    write(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-dependencies")
    export.add_argument("--output", type=Path, required=True)
    publication = commands.add_parser("publish")
    publication.add_argument("--native-report", type=Path, required=True)
    publication.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export-dependencies":
        return export_dependencies(args.output)
    return publish(args.native_report, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
