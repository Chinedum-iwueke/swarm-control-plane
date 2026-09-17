from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.task_runtime import fail_task
from app.schemas.task import TaskFailRequest


def test_retryable_approved_task_returns_for_renewed_approval() -> None:
    db = MagicMock()
    agent = SimpleNamespace(id=uuid4())
    task = SimpleNamespace(
        id=uuid4(),
        assigned_agent_id=agent.id,
        attempt_count=1,
        max_attempts=2,
        mission_id=None,
        approval_required=True,
        failure={},
        completed_at=None,
    )
    event = SimpleNamespace()
    now = datetime(2026, 9, 17, tzinfo=UTC)

    with (
        patch("app.api.routes.task_runtime.lock_task", return_value=task),
        patch("app.api.routes.task_runtime.verify_task_lease", return_value=now),
        patch("app.api.routes.task_runtime._append_terminal_event", return_value=event),
        patch("app.api.routes.task_runtime.rearm_task_approval") as rearm,
        patch("app.api.routes.task_runtime.append_task_event") as append,
        patch("app.api.routes.task_runtime._record_graph_task_message"),
        patch("app.api.routes.task_runtime.clear_lease"),
        patch("app.api.routes.task_runtime._reconcile_task_graph"),
        patch("app.api.routes.task_runtime.serialize_task", return_value={}),
        patch("app.api.routes.task_runtime.TaskResponse.model_validate"),
        patch("app.api.routes.task_runtime.TaskEventResponse.model_validate"),
        patch("app.api.routes.task_runtime.TaskMutationResponse"),
    ):
        fail_task(
            task.id,
            TaskFailRequest(
                lease_token="lease-token",
                message="Codex runtime failed before execution.",
                failure={"error_category": "runtime_error"},
                retryable=True,
            ),
            agent,
            db,
        )

    rearm.assert_called_once_with(
        db,
        task,
        "Retryable execution failure requires renewed approval.",
    )
    assert append.call_args.args[2] == "task_requeued"
    assert append.call_args.kwargs["payload"] == {"approval_required": True}
    db.commit.assert_called_once_with()
