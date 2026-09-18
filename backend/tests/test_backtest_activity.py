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


def test_commissioning_terminal_receipt_projects_native_evidence_without_promotion():
    item = task(stage="execute")
    item.input_contract["execution_class"] = "commissioning"
    item.result = {
        "summary": {
            "disposition": "commissioning_complete",
            "receipt_digest": "a" * 64,
            "execution_class": "commissioning",
            "qualification_authority": False,
            "metrics": {
                "declared_variant_count": 8,
                "selected_variant_index": 6,
                "oos_mean_net_r": -0.8,
            },
        },
        "downstream_handoff": {
            "publication_envelope": {
                "schema_version": "alpha003-publication-envelope-v1.0.0",
                "execution_class": "commissioning",
                "qualification_authority": False,
                "trial": {
                    "result_disposition": "rejected",
                    "bundle_digest": "b" * 64,
                    "bundle_manifest_digest": "c" * 64,
                    "representation_contract_digest": "d" * 64,
                    "market_model_bundle_digest": "e" * 64,
                    "search_plan_digest": "f" * 64,
                },
            },
            "producer_gate_report": {
                "failed_gates": ["positive_oos_net_edge"],
                "reproducible": True,
                "truth_certified": True,
                "qualification_authority": False,
                "shadow_eligible": False,
            },
        },
    }

    result = serialize_backtest(item)

    assert result["execution_evidence"] == "native_terminal_receipt"
    assert result["execution_class"] == "commissioning"
    assert result["qualification_authority"] is False
    assert result["outcome"] == "rejected"
    assert result["trial_count"] == 1
    assert result["failed_gates"] == ["positive_oos_net_edge"]
    assert result["gate_report"] == {
        "reproducible": True,
        "truth_certified": True,
        "shadow_eligible": False,
    }
    assert result["evidence_digests"] == [
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    ]
    assert result["promotion"] == "not_established"


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
