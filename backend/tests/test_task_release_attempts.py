from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.task_runtime import release_task
from app.schemas.task import TaskReleaseRequest


def _release(status: str, attempt_count: int, max_attempts: int = 2):
    db = MagicMock()
    agent = SimpleNamespace(id=uuid4())
    task = SimpleNamespace(
        id=uuid4(),
        status=status,
        assigned_agent_id=agent.id,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        mission_id=None,
        approval_required=False,
        cancel_requested_at=None,
        completed_at=None,
        failure={},
        task_graph_node_id=None,
    )
    event = SimpleNamespace()
    now = datetime(2026, 10, 3, tzinfo=UTC)

    with (
        patch("app.api.routes.task_runtime.lock_task", return_value=task),
        patch("app.api.routes.task_runtime.verify_task_lease", return_value=now),
        patch(
            "app.api.routes.task_runtime._append_terminal_event", return_value=event
        ) as append_terminal,
        patch("app.api.routes.task_runtime.rearm_task_approval") as rearm,
        patch("app.api.routes.task_runtime.append_task_event") as append,
        patch("app.api.routes.task_runtime.clear_lease"),
        patch("app.api.routes.task_runtime._reconcile_task_graph"),
        patch("app.api.routes.task_runtime.serialize_task", return_value={}),
        patch("app.api.routes.task_runtime.TaskResponse.model_validate"),
        patch("app.api.routes.task_runtime.TaskEventResponse.model_validate"),
        patch("app.api.routes.task_runtime.TaskMutationResponse"),
    ):
        release_task(
            task.id,
            TaskReleaseRequest(
                lease_token="lease-token",
                message="Worker policy rejected the workflow before start.",
            ),
            agent,
            db,
        )

    return task, append_terminal, append, rearm


def test_pre_start_release_does_not_consume_execution_attempt() -> None:
    task, append_terminal, append, rearm = _release("leased", attempt_count=2)

    assert task.attempt_count == 1
    assert task.status == "queued"
    assert task.completed_at is None
    assert append_terminal.call_args.kwargs["payload"] == {
        "previous_status": "leased",
        "resulting_status": "queued",
        "leased_attempt_number": 2,
        "attempt_consumed": False,
    }
    assert append.call_args.args[2] == "task_requeued"
    rearm.assert_called_once()


def test_post_start_release_still_consumes_execution_attempt() -> None:
    task, append_terminal, append, rearm = _release("running", attempt_count=2)

    assert task.attempt_count == 2
    assert task.status == "failed"
    assert task.failure["reason"] == "lease_released"
    assert append_terminal.call_args.kwargs["payload"]["attempt_consumed"] is True
    append.assert_not_called()
    rearm.assert_not_called()
