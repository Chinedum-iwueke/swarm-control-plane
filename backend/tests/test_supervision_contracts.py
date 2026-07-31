from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.services.supervision import (
    abort_supervision,
    approve_supervision,
    reconcile_mission,
)
from fastapi import HTTPException


def mission(**changes):
    value = SimpleNamespace(
        id=uuid4(),
        supervision_enabled=True,
        supervision_status="pending_approval",
        supervision_policy={
            "max_auto_recoveries": 2,
            "retry_backoff_seconds": 30,
            "retryable_categories": ["connection_error"],
        },
        manifest={"schema_version": 1},
        manifest_digest="",
        status="pending_approval",
        supervision_approved_at=None,
        supervision_approved_by=None,
        recovery_count=0,
        next_reconcile_at=None,
        supervision_exception={},
        deadline_at=datetime.now(UTC) + timedelta(hours=1),
        completed_at=None,
    )
    import hashlib
    import json

    value.manifest_digest = hashlib.sha256(
        json.dumps(value.manifest, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    for key, item in changes.items():
        setattr(value, key, item)
    return value


def test_supervised_plan_requires_matching_immutable_digest() -> None:
    value = mission(manifest_digest="0" * 64)
    with pytest.raises(HTTPException, match="digest"):
        approve_supervision(
            MagicMock(), value, actor="founder", reason="Approved plan."
        )


def test_supervised_plan_approval_activates_once() -> None:
    value = mission()
    db = MagicMock()
    approve_supervision(db, value, actor="founder", reason="Approved exact plan.")
    assert value.status == "active"
    assert value.supervision_status == "active"
    assert value.supervision_approved_by == "founder"
    with pytest.raises(HTTPException):
        approve_supervision(db, value, actor="founder", reason="Duplicate approval.")


def test_nonretryable_failure_requires_attention() -> None:
    value = mission(supervision_status="active", status="blocked")
    failed = SimpleNamespace(
        id=uuid4(),
        task_number="INF-01",
        status="failed",
        failure={"error_category": "policy_error", "retryable": False},
        attempt_count=1,
        max_attempts=2,
    )
    expired_rows = MagicMock()
    expired_rows.all.return_value = []
    status_rows = MagicMock()
    status_rows.all.return_value = ["failed"]
    task_rows = MagicMock()
    task_rows.all.return_value = [failed]
    db = MagicMock()
    db.get.return_value = value
    db.scalars.side_effect = [expired_rows, status_rows, task_rows]
    action, task_id = reconcile_mission(db, value)
    assert action == "attention_required"
    assert task_id == failed.id
    assert value.supervision_exception["category"] == "policy_error"


def test_recovery_never_exceeds_policy_budget() -> None:
    value = mission(
        supervision_status="active",
        status="blocked",
        recovery_count=2,
    )
    failed = SimpleNamespace(
        id=uuid4(),
        task_number="INF-01",
        status="failed",
        failure={"error_category": "connection_error", "retryable": True},
        attempt_count=1,
        max_attempts=3,
    )
    expired_rows = MagicMock()
    expired_rows.all.return_value = []
    status_rows = MagicMock()
    status_rows.all.return_value = ["failed"]
    task_rows = MagicMock()
    task_rows.all.return_value = [failed]
    db = MagicMock()
    db.get.return_value = value
    db.scalars.side_effect = [expired_rows, status_rows, task_rows]
    action, _ = reconcile_mission(db, value)
    assert action == "attention_required"
    assert value.supervision_exception["recovery_budget_available"] is False


def test_expired_mission_escalates_without_recovery() -> None:
    value = mission(
        supervision_status="active",
        status="active",
        deadline_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    expired_rows = MagicMock()
    expired_rows.all.return_value = []
    status_rows = MagicMock()
    status_rows.all.return_value = ["queued"]
    task_rows = MagicMock()
    task_rows.all.return_value = [SimpleNamespace(status="queued")]
    db = MagicMock()
    db.get.return_value = value
    db.scalars.side_effect = [expired_rows, status_rows, task_rows]
    action, task_id = reconcile_mission(db, value)
    assert action == "attention_required"
    assert task_id is None
    assert value.supervision_exception["category"] == "mission_deadline_exhausted"


def test_abort_preserves_history_and_cancels_queued_checkpoint() -> None:
    value = mission(supervision_status="recovering", status="active")
    task = SimpleNamespace(
        status="queued",
        completed_at=None,
        id=uuid4(),
        attempt_count=1,
    )
    rows = MagicMock()
    rows.all.return_value = [task]
    db = MagicMock()
    db.scalars.return_value = rows

    abort_supervision(
        db,
        value,
        actor="founder-operator",
        reason="Plan base commit changed after validation correction.",
    )

    assert task.status == "cancelled"
    assert value.status == "cancelled"
    assert value.supervision_status == "aborted"
    assert value.supervision_exception["category"] == "operator_abort"


def test_abort_refuses_running_checkpoint() -> None:
    value = mission(supervision_status="active", status="active")
    rows = MagicMock()
    rows.all.return_value = [SimpleNamespace(status="running")]
    db = MagicMock()
    db.scalars.return_value = rows
    with pytest.raises(HTTPException, match="Running"):
        abort_supervision(
            db,
            value,
            actor="founder-operator",
            reason="Operator requested a bounded abort.",
        )
