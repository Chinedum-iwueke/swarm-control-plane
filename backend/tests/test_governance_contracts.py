from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from app.schemas import ApprovalDecision, ArtifactCreate
from app.services.governance import approve_task, task_plan_digest
from pydantic import ValidationError


def test_plan_digest_is_canonical_and_changes_with_plan() -> None:
    first = task_plan_digest({"workflow": "validate", "risk": 1})
    reordered = task_plan_digest({"risk": 1, "workflow": "validate"})
    changed = task_plan_digest({"workflow": "validate", "risk": 2})
    assert first == reordered
    assert first != changed


def test_artifact_location_is_restricted_to_registered_schemes() -> None:
    common = {
        "lease_token": "lease-token",
        "artifact_type": "log",
        "name": "tests.stdout.log",
        "size_bytes": 10,
        "sha256": "a" * 64,
        "storage_backend": "workspace",
        "workflow": "code-validation",
        "workflow_version": "1.0.0",
        "source_commit": "b" * 40,
    }
    artifact = ArtifactCreate(location="workspace://logs/tests.log", **common)
    assert artifact.location.startswith("workspace://")
    with pytest.raises(ValidationError):
        ArtifactCreate(location="/etc/shadow", **common)


def test_approval_decision_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(
            actor="founder-operator",
            reason="Reviewed",
            expires_in_seconds=300,
            execution_command="sudo anything",
        )


def test_approval_emits_one_task_ready_transition() -> None:
    task = SimpleNamespace(
        id=uuid4(),
        status="pending_approval",
        task_number="OPS-READY-01",
        title="Approval race pilot",
        task_type="code_validation",
        plan_digest="a" * 64,
        attempt_count=0,
        mission_id=uuid4(),
    )
    approval = SimpleNamespace(
        id=uuid4(),
        task_id=task.id,
        status="pending",
        plan_digest=task.plan_digest,
    )
    mission = SimpleNamespace(supervision_enabled=True, next_reconcile_at=None)
    db = SimpleNamespace(
        get=lambda model, identifier: (
            mission if model.__name__ == "EngineeringMission" else task
        )
    )
    with (
        patch(
            "app.services.governance.append_approval_event",
            return_value=SimpleNamespace(id=7),
        ),
        patch("app.services.tasks.append_task_event") as task_event,
        patch(
            "app.services.founder_notifications.enqueue_task_ready"
        ) as enqueue,
    ):
        approve_task(
            db,
            approval,
            actor="founder",
            reason="Digest reviewed and approved.",
            expires_in_seconds=900,
        )

    assert task.status == "queued"
    assert mission.next_reconcile_at is not None
    task_event.assert_called_once()
    assert task_event.call_args.args[2] == "task_ready"
    enqueue.assert_called_once_with(db, task, approval, generation=7)
