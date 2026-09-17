from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from app.api.routes.tasks import rearm_expired_task_approval
from app.schemas.task import TaskResumeRequest
from fastapi import HTTPException


def task(status: str = "pending_approval", approval_required: bool = True):
    return SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        status=status,
        approval_required=approval_required,
        attempt_count=0,
    )


def test_expired_approval_can_be_rearmed_without_new_task() -> None:
    db = MagicMock()
    record = task()
    db.scalar.return_value = record
    event = SimpleNamespace()
    with (
        patch("app.api.routes.tasks.rearm_task_approval") as rearm,
        patch("app.api.routes.tasks.append_task_event", return_value=event),
        patch(
            "app.api.routes.tasks.serialize_task",
            return_value={
                "id": record.id,
                "task_number": "M11-1",
                "project": "bulletproof_bt",
                "task_type": "research_experiment",
                "title": "M11 trial",
                "objective": "Execute one prospectively registered research trial.",
                "status": "pending_approval",
                "priority": 65,
                "risk_level": 1,
                "assigned_agent_id": None,
                "parent_task_id": None,
                "mission_id": None,
                "milestone_step_id": None,
                "created_by": "founder-operator",
                "input_contract": {},
                "expected_outputs": [],
                "acceptance_criteria": [],
                "approval_policy": {},
                "approval_required": True,
                "plan_digest": "a" * 64,
                "required_capabilities": [],
                "allowed_machines": [],
                "max_attempts": 1,
                "attempt_count": 0,
                "leased_at": None,
                "lease_expires_at": None,
                "last_execution_heartbeat_at": None,
                "result": {},
                "failure": {},
                "created_at": "2026-07-31T00:00:00Z",
                "updated_at": "2026-07-31T00:00:00Z",
                "started_at": None,
                "completed_at": None,
            },
        ),
        patch(
            "app.api.routes.tasks.TaskEventResponse.model_validate", return_value=event
        ),
        patch(
            "app.api.routes.tasks.TaskMutationResponse",
            return_value=SimpleNamespace(task=SimpleNamespace(id=record.id)),
        ),
    ):
        response = rearm_expired_task_approval(
            record.id,
            TaskResumeRequest(requested_by="founder-operator", reason="Pilot delay."),
            db,
        )
    rearm.assert_called_once_with(db, record, "Pilot delay.")
    assert response.task.id == record.id
    db.commit.assert_called_once_with()


def test_rearm_rejects_non_pending_task() -> None:
    db = MagicMock()
    db.scalar.return_value = task(status="running")
    with pytest.raises(HTTPException, match="pending approval"):
        rearm_expired_task_approval(
            UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            TaskResumeRequest(requested_by="founder-operator", reason="No reason."),
            db,
        )


def test_stranded_queued_approval_can_be_rearmed() -> None:
    db = MagicMock()
    record = task(status="queued")
    db.scalar.return_value = record
    event = SimpleNamespace()
    with (
        patch("app.api.routes.tasks.rearm_task_approval") as rearm,
        patch("app.api.routes.tasks.append_task_event", return_value=event),
        patch(
            "app.api.routes.tasks.serialize_task",
            return_value={
                "id": record.id,
                "task_number": "A3-campaign-002-G2",
                "project": "bulletproof_bt",
                "task_type": "engineering_change",
                "title": "Implement the approved strategy",
                "objective": "Produce the exact native package.",
                "status": "pending_approval",
                "priority": 80,
                "risk_level": 1,
                "assigned_agent_id": None,
                "parent_task_id": None,
                "mission_id": None,
                "milestone_step_id": None,
                "created_by": "alpha-campaign-director",
                "input_contract": {},
                "expected_outputs": [],
                "acceptance_criteria": [],
                "approval_policy": {},
                "approval_required": True,
                "plan_digest": "a" * 64,
                "required_capabilities": [],
                "allowed_machines": [],
                "max_attempts": 2,
                "attempt_count": 1,
                "leased_at": None,
                "lease_expires_at": None,
                "last_execution_heartbeat_at": None,
                "result": {},
                "failure": {"retryable": True},
                "created_at": "2026-09-17T00:00:00Z",
                "updated_at": "2026-09-17T00:00:00Z",
                "started_at": None,
                "completed_at": None,
            },
        ),
        patch(
            "app.api.routes.tasks.TaskEventResponse.model_validate",
            return_value=event,
        ),
        patch(
            "app.api.routes.tasks.TaskMutationResponse",
            return_value=SimpleNamespace(task=SimpleNamespace(id=record.id)),
        ),
    ):
        response = rearm_expired_task_approval(
            record.id,
            TaskResumeRequest(
                requested_by="founder-operator",
                reason="Recover a queued task whose approval was consumed.",
            ),
            db,
        )

    rearm.assert_called_once_with(
        db, record, "Recover a queued task whose approval was consumed."
    )
    assert response.task.id == record.id
    db.commit.assert_called_once_with()
