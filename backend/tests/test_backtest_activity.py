from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.alpha_campaign import router
from app.services.backtest_activity import overview, serialize_backtest


def task(status="succeeded", stage="execute"):
    return SimpleNamespace(
        id=uuid4(),
        task_number="A3-test-E",
        title="A test",
        status=status,
        input_contract={
            "stage": stage,
            "tier": "Tier2B",
            "question": "Does lagged funding predict returns?",
            "campaign_id": str(uuid4()),
        },
        result={
            "summary": {
                "disposition": "engineering_required",
                "metrics": {"oos_trades": 70, "secret": "excluded"},
                "alpha_campaign_attempt": {
                    "outcome": "failed",
                    "trial_count": 0,
                    "gate_report": {
                        "shadow_eligible": True,
                        "failed_gates": ["missing_strategy"],
                    },
                },
            }
        },
        failure={},
        last_execution_heartbeat_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        completed_at=None,
    )


@pytest.mark.parametrize(
    "status,category",
    [
        ("pending_approval", "waiting"),
        ("queued", "waiting"),
        ("leased", "running"),
        ("running", "running"),
        ("failed", "finished"),
        ("succeeded", "finished"),
        ("cancelled", "finished"),
    ],
)
def test_preserves_task_state_and_native_outcome_without_inventing_promotion(
    status, category
):
    result = serialize_backtest(task(status))
    assert result["category"] == category
    assert result["status"] == status
    assert result["outcome"] == "failed"
    assert result["promotion"] == "not_established"
    assert result["trial_count"] == 0
    assert result["failed_gates"] == ["missing_strategy"]
    assert result["metrics"] == {"oos_trades": 70}


def test_drafting_success_is_not_execution_or_admission():
    result = serialize_backtest(
        task(stage="draft"), SimpleNamespace(phase="shadow", status="shadow_candidate")
    )
    assert result["execution_evidence"] == "no_native_terminal_receipt"
    assert result["promotion"] == "shadow_review_requested"


def test_activity_has_protected_static_route_before_campaign_id():
    assert router.dependencies
    paths = [route.path for route in router.routes]
    assert paths.index("/v1/research/alpha-campaigns/backtests/activity") < paths.index(
        "/v1/research/alpha-campaigns/{campaign_id}"
    )


def test_pagination_and_heartbeat_receipt_are_read_only():
    item = task("running")
    event = SimpleNamespace(
        task_id=item.id,
        payload={
            "progress": {
                "phase": "native_bulletproof_execution",
                "capacity_governed": True,
                "secret": "excluded",
            }
        },
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = [("running", 3)]
    db.scalar.return_value = 3
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [item]),
        SimpleNamespace(all=list),
        SimpleNamespace(all=lambda: [event]),
    ]
    result = overview(db, limit=1, offset=1, category="running", tier="Tier2B")
    assert result["has_more"] and result["total"] == 3
    assert result["offset"] == 1
    assert result["items"][0]["progress"] == {
        "phase": "native_bulletproof_execution",
        "capacity_governed": True,
    }
    db.commit.assert_not_called()
    db.add.assert_not_called()
