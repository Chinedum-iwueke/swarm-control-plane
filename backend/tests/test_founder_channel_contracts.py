from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.api.routes.founder_channel import _founder_approval
from app.core.config import get_settings
from app.core.security import require_founder_channel, require_orchestrator
from app.schemas import FounderChannelRequest


def credential(value: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


def test_founder_channel_credential_is_distinct_from_orchestrator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    founder = tmp_path / "founder"
    orchestrator = tmp_path / "orchestrator"
    founder.write_text("f" * 64)
    orchestrator.write_text("o" * 64)
    monkeypatch.setenv("FOUNDER_CHANNEL_SECRET_FILE", str(founder))
    monkeypatch.setenv("ORCHESTRATOR_SECRET_FILE", str(orchestrator))
    get_settings.cache_clear()
    require_founder_channel(credential("f" * 64))
    with pytest.raises(HTTPException):
        require_founder_channel(credential("o" * 64))
    require_orchestrator(credential("o" * 64))
    with pytest.raises(HTTPException):
        require_orchestrator(credential("f" * 64))
    get_settings.cache_clear()


def test_founder_intake_rejects_command_surface() -> None:
    with pytest.raises(ValidationError):
        FounderChannelRequest(
            kind="task",
            project="swarm-control-plane",
            title="Unsafe",
            objective="Attempt to carry an arbitrary command.",
            risk_level=0,
            acceptance_criteria=[],
            command="bash -c anything",
        )


class _Rows:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ApprovalDB:
    def __init__(self, task, mission, dependencies):
        self.task = task
        self.mission = mission
        self.dependencies = dependencies

    def get(self, model, identifier):
        return self.task if model.__name__ == "Task" else self.mission

    def execute(self, statement):
        return _Rows(self.dependencies)


def test_founder_approval_is_actionable_only_after_dependencies_succeed() -> None:
    now = datetime.now(UTC)
    task_id = uuid4()
    mission_id = uuid4()
    approval = SimpleNamespace(
        id=uuid4(),
        task_id=task_id,
        status="pending",
        plan_digest="a" * 64,
        risk_level=3,
        scope={"project": "invariance_research", "task_type": "infrastructure_operation"},
        requested_by="founder-operator",
        decided_by=None,
        decision_reason=None,
        issued_at=None,
        expires_at=None,
        consumed_at=None,
        created_at=now,
        updated_at=now,
    )
    task = SimpleNamespace(
        id=task_id,
        task_number="INF-RETRY-03",
        title="Retry: start-private",
        status="pending_approval",
        input_contract={"operation": "start-invariance-postgres-private"},
        milestone_step_id="start-private",
        mission_id=mission_id,
    )
    mission = SimpleNamespace(
        status="active",
        deadline_at=now + timedelta(hours=1),
    )

    blocked = _founder_approval(
        _ApprovalDB(task, mission, [("INF-RETRY-02", "running")]),
        approval,
    )
    actionable = _founder_approval(
        _ApprovalDB(task, mission, [("INF-RETRY-02", "succeeded")]),
        approval,
    )

    assert blocked.actionable is False
    assert blocked.blocked_by == ["INF-RETRY-02:running"]
    assert actionable.actionable is True
    assert actionable.blocked_by == []
