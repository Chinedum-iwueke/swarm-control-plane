from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.schemas.research_utilization import ResearchUtilizationSnapshotCreate
from app.services.research_utilization import (
    _reconcile_alert,
    current_status,
    record_snapshot,
)
from pydantic import ValidationError


def payload(state="fallback_research_running"):
    allocations = [
        {
            "queue_id": "queue-0001",
            "item_id": "family-0001",
            "item_type": "disc010_signal_screen",
            "priority": 10,
            "workers": 6,
            "locked_by": "capacity-director:1",
            "locked_at": "2026-09-29T20:00:00Z",
        }
    ]
    counts = {
        "governed_alpha_assignment": {"PENDING": 0, "LOCKED": 0, "DONE": 2, "FAILED": 1},
        "disc010_signal_screen": {"PENDING": 2, "LOCKED": 1, "DONE": 0, "FAILED": 0},
    }
    return {
        "schema_version": "research-utilization-snapshot-v1.0.0",
        "sample_id": "sample-0001",
        "machine": "vm1-developer",
        "observed_at": "2026-09-29T20:00:10Z",
        "state": state,
        "worker_budget": 12,
        "active_workers": 6,
        "queue_counts": {"PENDING": 2, "LOCKED": 1, "DONE": 2, "FAILED": 1},
        "work_kind_counts": counts,
        "allocations": allocations,
        "scheduler": {
            "hostname": "vm1",
            "pid": 123,
            "updated_at": "2026-09-29T20:00:09Z",
            "configured_worker_ceiling": 16,
            "resource_worker_budget": 12,
            "max_concurrent_jobs": 2,
            "max_workers_per_job": 8,
            "minimum_free_ram_gib": 8.0,
            "estimated_worker_ram_gib": 4.5,
            "available_ram_gib": 66.0,
            "paused_workers": 0,
            "external_locked_workers": 0,
        },
        "source_commits": {"control_plane": "a" * 40, "bulletproof": "b" * 40},
        "latest_completion_at": "2026-09-29T19:00:00Z",
        "action_authority": False,
        "capital_or_order_authority": False,
    }


def test_snapshot_requires_exact_worker_and_queue_accounting():
    value = payload()
    parsed = ResearchUtilizationSnapshotCreate.model_validate(value)
    assert parsed.active_workers == 6
    value["active_workers"] = 7
    with pytest.raises(ValidationError, match="allocated workers"):
        ResearchUtilizationSnapshotCreate.model_validate(value)


def test_fallback_state_cannot_hide_governed_backtest():
    value = payload()
    value["work_kind_counts"]["governed_alpha_assignment"]["LOCKED"] = 1
    value["queue_counts"]["LOCKED"] = 2
    value["allocations"].append(
        {
            "queue_id": "queue-0002",
            "item_id": "assignment-0002",
            "item_type": "governed_alpha_assignment",
            "priority": 50,
            "workers": 4,
            "locked_by": "capacity-director:2",
            "locked_at": "2026-09-29T20:00:00Z",
        }
    )
    value["active_workers"] = 10
    with pytest.raises(ValidationError, match="only locked signal screens"):
        ResearchUtilizationSnapshotCreate.model_validate(value)


def test_record_is_idempotent_and_has_no_action_authority():
    db = MagicMock()
    db.scalar.return_value = None
    parsed = ResearchUtilizationSnapshotCreate.model_validate(payload())
    result = record_snapshot(db, parsed)
    assert result.snapshot["capital_or_order_authority"] is False
    assert result.record_digest
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()


def test_current_status_marks_stale_and_computes_idle_workers():
    now = datetime.now(UTC)
    item = SimpleNamespace(
        id=uuid4(),
        machine="vm1-developer",
        observed_at=now - timedelta(minutes=6),
        state="eligible_queue_empty",
        worker_budget=12,
        active_workers=0,
        queue_counts={"PENDING": 0, "LOCKED": 0, "DONE": 8, "FAILED": 7},
        work_kind_counts={},
        allocations=[],
        scheduler={},
        source_commits={"control_plane": "a" * 40, "bulletproof": "b" * 40},
        record_digest="c" * 64,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [item]
    result = current_status(db)
    assert result["items"][0]["fresh"] is False
    assert result["items"][0]["idle_workers"] == 12
    db.commit.assert_not_called()


def test_three_consecutive_empty_snapshots_create_bounded_founder_alert():
    now = datetime.now(UTC)
    snapshots = [
        SimpleNamespace(
            id=uuid4(),
            machine="vm1-developer",
            state="eligible_queue_empty",
            observed_at=now - timedelta(minutes=offset),
            worker_budget=12,
            active_workers=0,
            queue_counts={"PENDING": 0, "LOCKED": 0},
            record_digest=str(offset) * 64,
        )
        for offset in range(3)
    ]
    db = MagicMock()
    db.scalars.return_value.all.return_value = snapshots
    db.scalar.return_value = None

    _reconcile_alert(db, snapshots[0])

    notification = db.add.call_args.args[0]
    assert notification.kind == "research_utilization_alert"
    assert notification.payload["action_authority"] is False
    assert notification.payload["worker_budget"] == 12
