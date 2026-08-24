from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.schemas.operation import OperationWrite
from app.services.operations import _task_state
from pydantic import ValidationError


def test_operation_contract_requires_honest_progress() -> None:
    with pytest.raises(ValidationError, match="requires current and total"):
        OperationWrite(
            operation_key="service:test",
            kind="test_operation",
            title="Test operation",
            project="swarm-control-plane",
            owner_type="service",
            state="running",
            phase="work",
            progress_mode="determinate",
        )
    with pytest.raises(ValidationError, match="cannot declare current or total"):
        OperationWrite(
            operation_key="service:test",
            kind="test_operation",
            title="Test operation",
            project="swarm-control-plane",
            owner_type="service",
            state="running",
            phase="work",
            progress_current=1,
        )


def test_task_reconciliation_distinguishes_approval_running_and_stalled() -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    pending = SimpleNamespace(status="pending_approval")
    assert _task_state(pending, now, 180) == ("waiting_approval", "approval")

    fresh = SimpleNamespace(
        status="running",
        last_execution_heartbeat_at=now - timedelta(seconds=30),
        started_at=now - timedelta(minutes=2),
        leased_at=None,
    )
    assert _task_state(fresh, now, 180) == ("running", "execution")

    stale = SimpleNamespace(
        status="running",
        last_execution_heartbeat_at=now - timedelta(seconds=181),
        started_at=now - timedelta(minutes=5),
        leased_at=None,
    )
    assert _task_state(stale, now, 180) == ("stalled", "execution")


def test_terminal_task_state_is_determinate() -> None:
    now = datetime.now(UTC)
    assert _task_state(SimpleNamespace(status="succeeded"), now, 180) == (
        "succeeded",
        "complete",
    )
    assert _task_state(SimpleNamespace(status="failed"), now, 180) == (
        "failed",
        "failed",
    )
