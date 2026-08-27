from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from app.api.routes.governance import approval_center_decision
from app.schemas.governance import ApprovalCenterDecision
from app.services.approval_center import (
    approval_center as build_approval_center,
)
from app.services.approval_center import (
    approval_center_item,
)
from fastapi import HTTPException

APPROVAL_ID = UUID("10000000-0000-4000-8000-000000000001")
TASK_ID = UUID("20000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 8, 27, tzinfo=UTC)
DIGEST = "a" * 64


def approval() -> SimpleNamespace:
    return SimpleNamespace(
        id=APPROVAL_ID,
        task_id=TASK_ID,
        status="pending",
        plan_digest=DIGEST,
        risk_level=3,
        scope={
            "project": "swarm-control-plane",
            "task_type": "infrastructure_operation",
            "input_contract": {"operation": "restart-api"},
        },
        requested_by="founder-operator",
        decided_by=None,
        decision_reason=None,
        issued_at=None,
        expires_at=None,
        consumed_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def task() -> SimpleNamespace:
    return SimpleNamespace(
        id=TASK_ID,
        task_number="UI004-LIVE-01",
        title="Digest-safe approval replay",
        objective="Exercise one exact approval review envelope.",
        project="swarm-control-plane",
        task_type="infrastructure_operation",
        status="pending_approval",
        risk_level=3,
        plan_digest=DIGEST,
        input_contract={"operation": "restart-api"},
        acceptance_criteria=["Exact digest is retained."],
        expected_outputs=["decision receipt"],
        required_capabilities=["controlled-restart"],
        allowed_machines=["vm2-deployment"],
        max_attempts=1,
        approval_required=True,
        mission_id=None,
    )


def center_db(record: SimpleNamespace, work: SimpleNamespace) -> MagicMock:
    db = MagicMock()
    db.get.side_effect = lambda model, identifier: (
        work if identifier == TASK_ID else None
    )
    db.execute.return_value.all.return_value = []
    db.scalar.return_value = None
    db.scalars.side_effect = [
        SimpleNamespace(all=list),
        SimpleNamespace(all=list),
    ]
    return db


def test_review_digest_is_current_and_actionable() -> None:
    record, work = approval(), task()
    item = approval_center_item(center_db(record, work), record)
    assert item["current"] is True
    assert item["executable"] is True
    assert item["actionable"] is True
    assert item["changed_fields"] == []
    assert len(item["review_digest"]) == 64


def test_changed_task_contract_fails_closed() -> None:
    record, work = approval(), task()
    work.input_contract = {"operation": "different-operation"}
    item = approval_center_item(center_db(record, work), record)
    assert item["current"] is False
    assert item["actionable"] is False
    assert item["changed_fields"] == ["input_contract"]
    assert item["blocked_by"][-1]["kind"] == "digest_mismatch"


def test_decision_rejects_superseded_review_digest() -> None:
    db = MagicMock()
    db.scalar.return_value = approval()
    payload = ApprovalCenterDecision(
        actor="founder-mission-control",
        reason="The exact displayed envelope was reviewed.",
        expected_review_digest="b" * 64,
    )
    with (
        patch(
            "app.api.routes.governance.approval_center_item",
            return_value={"review_digest": "c" * 64},
        ),
        pytest.raises(HTTPException, match="409"),
    ):
        approval_center_decision(APPROVAL_ID, "approve", payload, db)


def test_decision_retains_digest_bound_receipt() -> None:
    db = MagicMock()
    record = approval()
    db.scalar.return_value = record
    payload = ApprovalCenterDecision(
        actor="founder-mission-control",
        reason="The exact displayed envelope was reviewed.",
        expected_review_digest="d" * 64,
    )
    event = SimpleNamespace(id=91)
    with (
        patch(
            "app.api.routes.governance.approval_center_item",
            return_value={"review_digest": "d" * 64, "actionable": True},
        ),
        patch("app.api.routes.governance.resolve_task_approval"),
        patch("app.api.routes.governance.approve_task") as approve,
        patch(
            "app.api.routes.governance.append_approval_event", return_value=event
        ) as append,
    ):
        result = approval_center_decision(APPROVAL_ID, "approve", payload, db)
    assert result.review_digest == "d" * 64
    assert len(result.receipt_digest) == 64
    assert result.event_id == 91
    approve.assert_called_once()
    assert append.call_args.args[2] == "approval_center_decision_receipt"
    assert append.call_args.args[5]["review_digest"] == "d" * 64


def test_overview_keeps_all_pending_and_bounds_decision_history() -> None:
    pending = [SimpleNamespace(id="pending")]
    decided = [SimpleNamespace(id="decided")]
    db = MagicMock()
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: pending),
        SimpleNamespace(all=lambda: decided),
    ]
    db.execute.return_value.all.return_value = [
        ("pending", 1),
        ("approved", 40),
        ("rejected", 5),
    ]

    def item(record: SimpleNamespace) -> dict:
        is_pending = record.id == "pending"
        return {
            "approval": {"status": "pending" if is_pending else "approved"},
            "actionable": is_pending,
        }

    with patch(
        "app.services.approval_center.approval_center_item",
        side_effect=lambda _, record: item(record),
    ):
        result = build_approval_center(db)

    assert len(result["items"]) == 2
    assert result["counts"] == {
        "pending": 1,
        "actionable": 1,
        "blocked": 0,
        "decided": 45,
    }
