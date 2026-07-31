from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.api.routes.task_runtime import lease_task
from app.models import Agent
from app.schemas.task import TaskLeaseRequest
from app.services.tasks import lease_next_task


def test_lease_query_filters_invalid_approval_before_selection() -> None:
    db = MagicMock()
    agent = Agent(
        slug="test-agent",
        display_name="Test Agent",
        role="test",
        machine="vm1-developer",
        hermes_profile="test",
        capabilities=["testing"],
        risk_ceiling=1,
    )
    db.scalar.return_value = None
    with patch(
        "app.services.tasks.utc_now",
        return_value=datetime(2026, 7, 31, tzinfo=UTC),
    ):
        task, token, event = lease_next_task(db, agent, 300)

    assert (task, token, event) == (None, None, None)
    statement = db.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "task_approvals.status =" in sql
    assert "task_approvals.plan_digest = tasks.plan_digest" in sql
    assert "task_approvals.expires_at >" in sql
    assert "tasks.approval_required IS false" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_no_work_lease_commits_approval_expiry_reconciliation() -> None:
    db = MagicMock()
    agent = MagicMock()
    with (
        patch("app.api.routes.task_runtime.matching_control_scopes", return_value=[]),
        patch(
            "app.api.routes.task_runtime.lease_next_task",
            return_value=(None, None, None),
        ),
    ):
        response = lease_task(TaskLeaseRequest(), agent, db)

    assert response.task is None
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
