from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.task_runtime import defer_provider_capacity, lease_task
from app.schemas.provider_capacity import ProviderCapacityDeferral
from app.schemas.task import TaskLeaseRequest
from app.services.provider_capacity import claim_due_probes_or_block, report_probe


def _circuit(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "provider": "codex",
        "state": "open",
        "generation": 1,
        "consecutive_failures": 1,
        "blocked_capabilities": ["alpha-strategy-engineering", "testing"],
        "failure_summary": "usage limit reached",
        "source_task_id": uuid4(),
        "probe_agent_id": None,
        "opened_at": now,
        "next_probe_at": now + timedelta(minutes=15),
        "probe_expires_at": None,
        "recovered_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _agent(**overrides):
    values = {
        "id": uuid4(),
        "slug": "vm1-alpha-strategy-engineer",
        "capabilities": ["alpha-strategy-engineering", "testing", "git", "python"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_open_circuit_blocks_only_matching_provider_workers() -> None:
    circuit = _circuit()
    db = MagicMock()
    db.scalars.return_value.all.return_value = [circuit]

    probes, reasons = claim_due_probes_or_block(db, _agent())
    deterministic_probes, deterministic_reasons = claim_due_probes_or_block(
        db,
        _agent(
            slug="vm1-data-admission",
            capabilities=["alpha-data-admission"],
        ),
    )

    assert probes == []
    assert reasons and "codex provider capacity circuit" in reasons[0]
    assert deterministic_probes == []
    assert deterministic_reasons == []


def test_due_probe_is_claimed_by_one_matching_agent() -> None:
    circuit = _circuit(next_probe_at=datetime.now(UTC) - timedelta(seconds=1))
    agent = _agent()
    db = MagicMock()
    db.scalars.return_value.all.return_value = [circuit]

    probes, reasons = claim_due_probes_or_block(db, agent)

    assert probes == ["codex"]
    assert reasons == []
    assert circuit.state == "half_open"
    assert circuit.probe_agent_id == agent.id
    assert circuit.probe_expires_at > datetime.now(UTC)


def test_empty_task_queue_does_not_claim_due_provider_probe() -> None:
    circuit = _circuit(next_probe_at=datetime.now(UTC) - timedelta(seconds=1))
    db = MagicMock()
    db.scalars.return_value.all.return_value = [circuit]
    with (
        patch("app.api.routes.task_runtime.matching_control_scopes", return_value=[]),
        patch("app.api.routes.task_runtime.reap_expired_leases"),
        patch(
            "app.api.routes.task_runtime.lease_next_task",
            return_value=(None, None, None, {}),
        ),
    ):
        response = lease_task(TaskLeaseRequest(lease_seconds=300), _agent(), db)

    assert response.task is None
    assert response.provider_probes == []
    assert circuit.state == "open"
    assert circuit.probe_agent_id is None
    db.add.assert_not_called()
    db.commit.assert_called_once()


def test_capacity_check_keeps_due_probe_available_until_task_selection() -> None:
    circuit = _circuit(next_probe_at=datetime.now(UTC) - timedelta(seconds=1))
    db = MagicMock()
    db.scalars.return_value.all.return_value = [circuit]
    agent = _agent()
    assert claim_due_probes_or_block(db, agent, claim=False) == ([], [])
    assert circuit.state == "open"
    db.add.assert_not_called()
    assert claim_due_probes_or_block(db, agent) == (["codex"], [])
    assert circuit.state == "half_open"


def test_healthy_probe_closes_circuit_and_supersedes_notification() -> None:
    agent = _agent()
    circuit = _circuit(state="half_open", probe_agent_id=agent.id)
    notification = SimpleNamespace(
        state="pending", superseded_at=None, updated_at=datetime.now(UTC)
    )
    db = MagicMock()
    db.scalar.return_value = circuit
    db.scalars.return_value.all.return_value = [notification]

    result = report_probe(
        db,
        provider="codex",
        agent=agent,
        healthy=True,
        failure_summary=None,
        retry_after_seconds=900,
    )

    assert result.state == "closed"
    assert result.next_probe_at is None
    assert result.consecutive_failures == 0
    assert notification.state == "superseded"


def test_capacity_deferral_restores_attempt_and_requeues_task() -> None:
    agent = _agent()
    task = SimpleNamespace(
        id=uuid4(),
        task_number="A3-TEST-G1",
        status="running",
        assigned_agent_id=agent.id,
        attempt_count=2,
        required_capabilities=["alpha-strategy-engineering", "testing"],
        failure={"old": "failure"},
        completed_at=datetime.now(UTC),
    )
    event = SimpleNamespace()
    circuit = _circuit()
    db = MagicMock()

    with (
        patch("app.api.routes.task_runtime.lock_task", return_value=task),
        patch("app.api.routes.task_runtime.verify_task_lease"),
        patch(
            "app.api.routes.task_runtime._append_terminal_event", return_value=event
        ),
        patch("app.api.routes.task_runtime.clear_lease") as clear,
        patch(
            "app.api.routes.task_runtime.open_circuit",
            return_value=(circuit, True),
        ),
        patch("app.api.routes.task_runtime.serialize_task", return_value={}),
        patch("app.api.routes.task_runtime.TaskResponse.model_validate"),
        patch("app.api.routes.task_runtime.TaskEventResponse.model_validate"),
        patch(
            "app.api.routes.task_runtime.ProviderCapacityCircuitResponse.model_validate"
        ),
        patch("app.api.routes.task_runtime.ProviderCapacityDeferralResponse"),
    ):
        defer_provider_capacity(
            task.id,
            ProviderCapacityDeferral(
                lease_token="lease-token",
                provider="codex",
                failure_summary="usage limit reached",
            ),
            agent,
            db,
        )

    assert task.attempt_count == 1
    assert task.status == "queued"
    assert task.failure == {}
    assert task.completed_at is None
    clear.assert_called_once_with(task)
