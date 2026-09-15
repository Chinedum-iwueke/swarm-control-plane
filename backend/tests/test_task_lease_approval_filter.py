from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.routes.task_runtime import lease_task
from app.models import Agent
from app.schemas.task import TaskLeaseRequest
from app.services.tasks import lease_next_task
from sqlalchemy.dialects import postgresql


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
    db.scalars.return_value.all.return_value = []
    with patch(
        "app.services.tasks.utc_now",
        return_value=datetime(2026, 7, 31, tzinfo=UTC),
    ):
        task, token, event = lease_next_task(db, agent, 300)

    assert (task, token, event) == (None, None, None)
    statement = db.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "task_approvals.status =" in sql
    assert "task_approvals.plan_digest = tasks.plan_digest" in sql
    assert "task_approvals.expires_at >" in sql
    assert "tasks.approval_required IS false" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "tasks.task_type !=" in sql
    assert "tasks.input_contract ->>" in sql
    params = statement.compile(dialect=postgresql.dialect()).params
    assert "alpha_strategy_review" in params.values()
    assert "evaluator_agent_id" in params.values()


def test_authority_denied_task_does_not_starve_later_authorized_work() -> None:
    db = MagicMock()
    agent = Agent(
        id="11111111-1111-4111-8111-111111111111",
        slug="test-agent",
        display_name="Test Agent",
        role="test",
        machine="vm1-developer",
        hermes_profile="test",
        capabilities=["founder-intake"],
        risk_ceiling=1,
    )
    denied = SimpleNamespace(id="denied", required_capabilities=["founder-intake"])
    allowed = SimpleNamespace(
        id="allowed",
        operation_type="founder_intake_plan",
        input_contract={},
        required_capabilities=["founder-intake"],
        approval_required=False,
        status="queued",
        assigned_agent_id=None,
        attempt_count=0,
        leased_at=None,
        lease_expires_at=None,
        lease_token_prefix=None,
        lease_token_digest=None,
    )
    no_expired_approvals = MagicMock()
    no_expired_approvals.all.return_value = []
    lease_candidates = MagicMock()
    lease_candidates.all.return_value = [denied, allowed]
    db.scalars.side_effect = [no_expired_approvals, lease_candidates]
    db.scalar.return_value = None

    with (
        patch(
            "app.services.tasks.resolve_task_authority",
            side_effect=[
                [{"allowed": False, "reasons": ["legacy-grant-denied"]}],
                [
                    {
                        "allowed": True,
                        "reasons": [],
                        "snapshot_digest": "authority-snapshot",
                        "charter_digest": "charter",
                        "package_digest": "package",
                        "grant_digest": "grant",
                        "accountable_owner": "founder-operator",
                    }
                ],
            ],
        ),
        patch(
            "app.services.tasks.create_task_lease_token",
            return_value=SimpleNamespace(
                token="lease-token", prefix="lease", digest="lease-digest"
            ),
        ),
        patch("app.services.tasks.consume_task_approval"),
        patch("app.services.tasks.append_task_event") as append_event,
    ):
        task, token, _event = lease_next_task(db, agent, 300)

    assert task is allowed
    assert token is not None
    assert allowed.status == "leased"
    assert append_event.call_args_list[0].args[1] is denied
    assert append_event.call_args_list[0].args[2] == "task_authority_denied"


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
