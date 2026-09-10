from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.task_runtime import _append_terminal_event


def test_terminal_event_is_complete_before_append() -> None:
    db = MagicMock()
    task = SimpleNamespace(id=uuid4())
    agent_id = uuid4()
    event = SimpleNamespace(payload={})

    with (
        patch(
            "app.services.agent_context.discard_working_memory",
            return_value=3,
        ) as discard,
        patch(
            "app.api.routes.task_runtime.append_task_event",
            return_value=event,
        ) as append,
    ):
        result = _append_terminal_event(
            db,
            task,
            "task_completed",
            "Task completed successfully.",
            agent_id=agent_id,
            payload={"result": {"ok": True}},
        )

    assert result is event
    discard.assert_called_once_with(db, task.id)
    assert append.call_args.kwargs["payload"] == {
        "result": {"ok": True},
        "working_memory_discarded": 3,
    }
    assert event.payload == {}
