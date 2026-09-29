import json
import sqlite3
from pathlib import Path

from worker.scripts.research_utilization_publish import load_snapshot


def create_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE queues (
          id TEXT, queue_name TEXT, item_type TEXT, item_id TEXT, status TEXT,
          priority INTEGER, payload_json TEXT, created_at TEXT, updated_at TEXT,
          locked_at TEXT, locked_by TEXT
        )
        """
    )
    connection.executemany(
        "INSERT INTO queues VALUES (?, 'approved_backtests', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "q1", "disc010_signal_screen", "screen-1", "LOCKED", 10,
                json.dumps({"max_workers": 6}), "2026-09-29T19:00:00Z",
                "2026-09-29T19:01:00Z", "2026-09-29T19:00:01Z", "slot-1",
            ),
            (
                "q2", "disc010_signal_screen", "screen-2", "PENDING", 10,
                json.dumps({"max_workers": 6}), "2026-09-29T19:00:00Z",
                "2026-09-29T19:01:00Z", None, None,
            ),
        ],
    )
    connection.commit()
    connection.close()


def test_load_snapshot_reports_productive_fallback_capacity(tmp_path):
    database = tmp_path / "capacity.sqlite"
    state = tmp_path / "state.json"
    create_database(database)
    state.write_text(
        json.dumps(
            {
                "hostname": "vm1",
                "pid": 123,
                "updated_at": "2026-09-29T19:01:00Z",
                "config": {"target_workers": 12, "max_concurrent_jobs": 2, "max_workers_per_job": 6},
                "worker_slots": {"target": 12, "paused": 0, "external_locked": 0},
                "memory": {"available_gb": 40},
            }
        ),
        encoding="utf-8",
    )
    result = load_snapshot(
        database=database,
        state_path=state,
        machine="vm1-developer",
        control_commit="a" * 40,
        bulletproof_commit="b" * 40,
    )
    assert result["state"] == "fallback_research_running"
    assert result["active_workers"] == 6
    assert result["queue_counts"]["PENDING"] == 1
    assert result["allocations"][0]["item_type"] == "disc010_signal_screen"
    assert result["capital_or_order_authority"] is False
