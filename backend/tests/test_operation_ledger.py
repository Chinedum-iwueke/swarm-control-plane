from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.operation import OperationWrite
from app.services.operations import _task_state
from pydantic import ValidationError


def test_active_operations_are_not_hidden_by_recent_terminal_history(monkeypatch):
    import sqlite3

    from app.api.routes.operations import list_operations
    from app.models.operation import Operation
    from sqlalchemy import select
    from sqlalchemy.dialects import sqlite

    monkeypatch.setattr("app.api.routes.operations.reconcile_task_operations", lambda db: None)
    monkeypatch.setattr("app.api.routes.operations.mark_stalled_operations", lambda db: None)
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    list_operations(db, states=None, limit=2)
    original = db.scalars.call_args.args[0]
    statement = select(Operation.operation_key).order_by(*original._order_by_clauses).limit(2)
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE operations (operation_key TEXT, state TEXT, updated_at TEXT)")
        connection.executemany("INSERT INTO operations VALUES (?, ?, ?)", [
            ("old-live-scan", "running", "2026-09-15T20:00:00"),
            ("recent-history-one", "succeeded", "2026-09-15T21:00:00"),
            ("recent-history-two", "failed", "2026-09-15T21:01:00"),
        ])
        query = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        rows = connection.execute(query).fetchall()
    assert rows[0] == ("old-live-scan",)


@pytest.mark.parametrize("kind", ["full_lake_inventory", "backtest"])
def test_inventory_report_cannot_rewrite_other_workloads(monkeypatch, kind):
    from app.api.routes.operations import report_lake_inventory
    from fastapi import HTTPException

    payload = OperationWrite(operation_key="lake-inventory:test", kind=kind,
                             title="Full lake inventory", project="bulletproof-bt",
                             machine="vm1-developer", owner_type="system", owner_id="founder-operator",
                             state="running", phase="hashing", input_digest="a" * 64)
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


@pytest.mark.parametrize("mutation", ["inputs", "resurrection", "repeat"])
def test_inventory_reports_preserve_run_binding_and_terminal_state(monkeypatch, mutation):
    from app.api.routes.operations import report_lake_inventory
    from fastapi import HTTPException
    previous = SimpleNamespace(kind="full_lake_inventory", input_digest="a" * 64, state="succeeded")
    payload = OperationWrite(operation_key="lake-inventory:test", kind="full_lake_inventory",
                             title="Full lake inventory", project="bulletproof-bt",
                             machine="vm1-developer", owner_type="system", owner_id="founder-operator",
                             state="running" if mutation == "resurrection" else "succeeded", phase="complete",
                             input_digest=("b" if mutation == "inputs" else "a") * 64)
    db = MagicMock()
    db.scalar.return_value = previous
    write = MagicMock()
    monkeypatch.setattr("app.api.routes.operations.upsert_operation", write)
    if mutation == "repeat":
        assert report_lake_inventory(payload, db) is previous
    else:
        with pytest.raises(HTTPException) as error:
            report_lake_inventory(payload, db)
        assert error.value.status_code == 409
    write.assert_not_called()
    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is not None


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
