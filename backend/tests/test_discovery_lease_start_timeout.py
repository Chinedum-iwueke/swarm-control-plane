from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services import tasks


@pytest.mark.parametrize("exhausted", [False, True])
def test_unacknowledged_discovery_is_fenced_and_retry_budget_preserved(monkeypatch, exhausted):
    now = datetime.now(UTC)
    task = SimpleNamespace(assigned_agent_id="worker", status="leased",
        lease_expires_at=now+timedelta(minutes=20),attempt_count=2 if exhausted else 1,
        max_attempts=2,failure={})
    db = MagicMock()
    db.scalars.return_value.all.return_value = [task]
    monkeypatch.setattr(tasks, "utc_now", lambda:now)
    event, clear, rearm = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(tasks, "append_task_event", event)
    monkeypatch.setattr(tasks, "clear_lease", clear)
    monkeypatch.setattr(tasks, "rearm_task_approval", rearm)
    assert tasks.reap_expired_leases(db) == (1, 0 if exhausted else 1, 1 if exhausted else 0)
    clear.assert_called_once_with(task)
    assert task.attempt_count == (2 if exhausted else 1)
    assert event.call_args_list[0].args[2] == "lease_start_timeout"
    if exhausted:
        assert task.status == "failed"
        assert task.failure["reason"] == "lease_start_timeout"
        rearm.assert_not_called()
    else:
        rearm.assert_called_once()
    statement = db.scalars.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(statement)
    assert "tasks.last_execution_heartbeat_at = tasks.leased_at" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "alpha_discovery" in statement.params.values()
    assert "leased" in statement.params.values()
    assert now - timedelta(minutes=5) in statement.params.values()


def test_expired_running_lease_keeps_existing_expiry_semantics(monkeypatch):
    now = datetime.now(UTC)
    task = SimpleNamespace(assigned_agent_id="worker", status="running",
        lease_expires_at=now-timedelta(seconds=1),attempt_count=2,max_attempts=2,failure={})
    db = MagicMock()
    db.scalars.return_value.all.return_value = [task]
    monkeypatch.setattr(tasks,"utc_now",lambda:now)
    monkeypatch.setattr(tasks,"append_task_event",MagicMock())
    monkeypatch.setattr(tasks,"clear_lease",MagicMock())
    assert tasks.reap_expired_leases(db) == (1,0,1)
    assert task.failure["reason"] == "lease_expired"
