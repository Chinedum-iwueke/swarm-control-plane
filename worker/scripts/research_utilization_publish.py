#!/usr/bin/env python3
"""Publish the native Bulletproof capacity queue as bounded Hermes telemetry."""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

STATUSES = ("PENDING", "LOCKED", "DONE", "FAILED")
ITEM_TYPES = ("governed_alpha_assignment", "disc010_signal_screen")


def read_secret(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"credential file is empty: {path}")
    return value


def load_snapshot(
    *,
    database: Path,
    state_path: Path,
    machine: str,
    control_commit: str,
    bulletproof_commit: str,
) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    observed_at = datetime.now(UTC)
    uri = f"file:{database.resolve(strict=True)}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT id, item_id, item_type, status, priority, payload_json,
                   locked_by, locked_at, updated_at
            FROM queues
            WHERE queue_name = 'approved_backtests'
              AND item_type IN ('governed_alpha_assignment', 'disc010_signal_screen')
            ORDER BY created_at, id
            """
        ).fetchall()
    finally:
        connection.close()

    work_kind_counts = {
        item_type: {status: 0 for status in STATUSES} for item_type in ITEM_TYPES
    }
    allocations = []
    latest_completion_at = None
    for row in rows:
        status = str(row["status"])
        item_type = str(row["item_type"])
        if status not in STATUSES or item_type not in ITEM_TYPES:
            continue
        work_kind_counts[item_type][status] += 1
        if status in {"DONE", "FAILED"} and (
            latest_completion_at is None or row["updated_at"] > latest_completion_at
        ):
            latest_completion_at = row["updated_at"]
        if status != "LOCKED":
            continue
        payload = json.loads(row["payload_json"])
        allocations.append(
            {
                "queue_id": row["id"],
                "item_id": row["item_id"],
                "item_type": item_type,
                "priority": int(row["priority"]),
                "workers": int(payload["max_workers"]),
                "locked_by": row["locked_by"],
                "locked_at": row["locked_at"],
            }
        )

    queue_counts = {
        status: sum(counts[status] for counts in work_kind_counts.values())
        for status in STATUSES
    }
    active_workers = sum(item["workers"] for item in allocations)
    worker_slots = state.get("worker_slots") or {}
    config = state.get("config") or {}
    configured_workers = int(
        worker_slots.get("target", config.get("target_workers", 0))
    )
    available_ram = float((state.get("memory") or {}).get("available_gb", 0))
    minimum_free_ram = float(config.get("min_free_ram_gb", 0))
    worker_ram = max(float(config.get("estimated_worker_ram_gb", 0)), 0.001)
    memory_budget = max(0, math.floor((available_ram - minimum_free_ram) / worker_ram))
    cpu_budget = max(0, (os.cpu_count() or 1) - 2)
    resource_worker_budget = min(configured_workers, memory_budget, cpu_budget)
    worker_budget = max(active_workers, resource_worker_budget)
    pending = queue_counts["PENDING"]
    governed_locked = work_kind_counts["governed_alpha_assignment"]["LOCKED"]
    screen_locked = work_kind_counts["disc010_signal_screen"]["LOCKED"]
    paused = int(worker_slots.get("paused", 0))
    if governed_locked:
        utilization_state = "approved_backtests_running"
    elif screen_locked:
        utilization_state = "fallback_research_running"
    elif pending and (paused or resource_worker_budget == 0):
        utilization_state = "resource_blocked"
    elif pending:
        utilization_state = "work_queued"
    else:
        utilization_state = "eligible_queue_empty"

    return {
        "schema_version": "research-utilization-snapshot-v1.0.0",
        "sample_id": f"{int(observed_at.timestamp())}-{uuid.uuid4().hex[:12]}",
        "machine": machine,
        "observed_at": observed_at.isoformat(),
        "state": utilization_state,
        "worker_budget": worker_budget,
        "active_workers": active_workers,
        "queue_counts": queue_counts,
        "work_kind_counts": work_kind_counts,
        "allocations": allocations,
        "scheduler": {
            "hostname": state.get("hostname", socket.gethostname()),
            "pid": state.get("pid"),
            "updated_at": state.get("updated_at"),
            "configured_worker_ceiling": configured_workers,
            "resource_worker_budget": resource_worker_budget,
            "max_concurrent_jobs": int(config.get("max_concurrent_jobs", 0)),
            "max_workers_per_job": int(config.get("max_workers_per_job", 0)),
            "minimum_free_ram_gib": minimum_free_ram,
            "estimated_worker_ram_gib": worker_ram,
            "available_ram_gib": available_ram,
            "paused_workers": paused,
            "external_locked_workers": int(worker_slots.get("external_locked", 0)),
        },
        "source_commits": {
            "control_plane": control_commit,
            "bulletproof": bulletproof_commit,
        },
        "latest_completion_at": latest_completion_at,
        "action_authority": False,
        "capital_or_order_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--control-commit", required=True)
    parser.add_argument("--bulletproof-commit", required=True)
    parser.add_argument("--api-url-file", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    payload = load_snapshot(
        database=args.database,
        state_path=args.state,
        machine=args.machine,
        control_commit=args.control_commit,
        bulletproof_commit=args.bulletproof_commit,
    )
    api_url = read_secret(args.api_url_file).rstrip("/").removesuffix("/v1")
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {read_secret(args.token_file)}"},
        timeout=60,
    ) as client:
        response = client.post("/v1/research/utilization/snapshots", json=payload)
        response.raise_for_status()
    print(
        json.dumps(
            {
                "event": "research_utilization_snapshot_published",
                "machine": payload["machine"],
                "state": payload["state"],
                "active_workers": payload["active_workers"],
                "worker_budget": payload["worker_budget"],
                "pending": payload["queue_counts"]["PENDING"],
                "locked": payload["queue_counts"]["LOCKED"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
