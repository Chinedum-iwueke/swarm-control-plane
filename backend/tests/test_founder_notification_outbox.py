from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.founder_notifications import (
    acknowledge_notification,
    reconcile_founder_notifications,
)


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class DB:
    def __init__(self, scalar_groups, event, task=None):
        self.scalar_groups = iter(scalar_groups)
        self.event = event
        self.task = task

    def scalars(self, statement):
        return Rows(next(self.scalar_groups))

    def scalar(self, statement):
        return self.event

    def get(self, model, identifier):
        return self.task

    def flush(self):
        return None


def test_five_pending_approvals_activate_only_the_actionable_gate() -> None:
    approvals = [
        SimpleNamespace(
            id=uuid4(),
            status="pending",
            plan_digest=str(index) * 64,
            risk_level=3,
        )
        for index in range(1, 6)
    ]
    tasks = [
        SimpleNamespace(
            task_number=f"OPS-{index}",
            title=f"Gate {index}",
            input_contract={},
            task_type="infrastructure_operation",
        )
        for index in range(1, 6)
    ]
    readiness = [
        (index == 0, [] if index == 0 else ["prior:queued"], tasks[index], None)
        for index in range(5)
    ]
    db = DB([[], approvals, [], [], [], []], SimpleNamespace(id=41))
    with (
        patch(
            "app.services.founder_notifications.approval_readiness",
            side_effect=readiness,
        ),
        patch(
            "app.services.founder_notifications._insert_once",
            side_effect=lambda database, value: value,
        ) as insert,
    ):
        reconcile_founder_notifications(db)  # type: ignore[arg-type]

    assert insert.call_count == 5
    notifications = [call.args[1] for call in insert.call_args_list]
    assert notifications[0].payload["task_number"] == "OPS-1"
    assert notifications[0].deduplication_key.endswith(":41")
    assert [item.state for item in notifications] == [
        "pending",
        "waiting",
        "waiting",
        "waiting",
        "waiting",
    ]


def test_stale_pending_gate_is_superseded() -> None:
    now = datetime.now(UTC)
    stale = SimpleNamespace(
        state="pending",
        kind="approval_required",
        deduplication_key="approval:stale",
        superseded_at=None,
        updated_at=now,
    )
    db = DB([[], [], [], [stale], [], []], None)

    assert reconcile_founder_notifications(db) == []  # type: ignore[arg-type]
    assert stale.state == "superseded"
    assert stale.superseded_at is not None


def test_task_ready_message_is_superseded_after_lease() -> None:
    ready = SimpleNamespace(
        state="pending",
        kind="task_ready",
        entity_id=uuid4(),
        superseded_at=None,
        updated_at=None,
    )
    db = DB(
        [[], [], [], [], [ready], []],
        None,
        task=SimpleNamespace(status="leased"),
    )

    assert reconcile_founder_notifications(db) == []  # type: ignore[arg-type]
    assert ready.state == "superseded"


def test_acknowledgement_is_idempotent_and_rejects_superseded_gate() -> None:
    pending = SimpleNamespace(
        state="pending", acknowledged_by=None, acknowledged_at=None, updated_at=None
    )
    acknowledge_notification(pending, "telegram:456")
    acknowledged_at = pending.acknowledged_at
    acknowledge_notification(pending, "telegram:456")

    assert pending.state == "acknowledged"
    assert pending.acknowledged_at == acknowledged_at
    assert pending.acknowledged_by == "telegram:456"
