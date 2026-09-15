from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.operation import OperationWrite
from app.services.operations import _task_state
from pydantic import ValidationError


@pytest.mark.parametrize("kind", ["full_lake_inventory", "backtest"])
def test_inventory_report_cannot_rewrite_other_workloads(monkeypatch, kind):
    from app.api.routes.operations import report_lake_inventory
    from fastapi import HTTPException

    payload = OperationWrite(operation_key="lake-inventory:test", kind=kind,
                             title="Full lake inventory", project="bulletproof-bt",
                             machine="vm1-developer", owner_type="system", owner_id="founder-operator",
                             state="running", phase="hashing")
    db = MagicMock()
    db.scalar.return_value = None
    write = MagicMock(return_value=SimpleNamespace(kind=kind))
    monkeypatch.setattr("app.api.routes.operations.upsert_operation", write)
    if kind == "backtest":
        with pytest.raises(HTTPException) as error:
            report_lake_inventory(payload, db)
        assert error.value.status_code == 422
        write.assert_not_called()
    else:
        assert report_lake_inventory(payload, db).kind == "full_lake_inventory"
        write.assert_called_once()


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
