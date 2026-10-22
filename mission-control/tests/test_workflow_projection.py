from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_mission_control.workflow_projection import project_workflows

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def operation(**overrides):
    value = {
        "id": "op-1",
        "operation_key": "task:op-1",
        "kind": "research_experiment",
        "title": "Run a bounded experiment",
        "project": "bulletproof_bt",
        "machine": "vm1-developer",
        "owner_type": "task",
        "owner_id": "task-1",
        "state": "running",
        "phase": "execute",
        "heartbeat_at": "2026-10-22T11:59:30+00:00",
        "updated_at": "2026-10-22T11:59:30+00:00",
        "retryable": False,
        "input_digest": "a" * 64,
        "record_digest": "b" * 64,
        "detail": {"workflow": "bulletproof", "workflow_version": "1.0.0"},
        "links": {},
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("state", "phase", "expected_state", "blocker"),
    [
        ("running", "execute", "running", None),
        ("waiting_approval", "approval", "waiting_approval", None),
        ("blocked", "waiting_data", "blocked", "missing_dataset"),
        ("stalled", "execute", "stalled", "heartbeat_late"),
        ("failed", "failed", "failed", None),
        ("cancelled", "complete", "cancelled", None),
        ("succeeded", "complete", "succeeded", None),
    ],
)
def test_operation_projection_covers_workflow_terminal_and_waiting_paths(
    state, phase, expected_state, blocker
):
    detail = {"workflow": "bulletproof", "workflow_version": "1.0.0"}
    if blocker:
        detail["blockers"] = [blocker]
    if state == "succeeded":
        detail["terminal_receipt"] = "receipt-1"
    item = project_workflows(
        {"operations": [operation(state=state, phase=phase, detail=detail)]}, now=NOW
    )["items"][0]
    assert item["state"] == expected_state
    assert item["workflow"] == {"name": "bulletproof", "version": "1.0.0"}
    assert item["stages"][0] == {"name": phase, "state": expected_state}
    assert item["blockers"] == ([blocker] if blocker else [])
    assert item["terminal_outcome"] == (
        state if state in {"failed", "cancelled", "succeeded"} else None
    )
    if state == "succeeded":
        assert item["exit_evidence"]["digest"] == "receipt-1"


def test_stale_heartbeat_fails_closed_to_stalled():
    item = project_workflows(
        {"operations": [operation(heartbeat_at="2026-10-22T11:50:00+00:00")]},
        now=NOW,
    )["items"][0]
    assert item["state"] == "stalled"
    assert item["stale"] is True


def test_campaign_running_does_not_claim_native_backtest_without_live_leaf():
    snapshot = {
        "alpha_campaigns": [
            {
                "id": "campaign-1",
                "campaign_key": "cross-asset-lead-lag",
                "status": "running",
                "phase": "strategy_engineering",
                "campaign_digest": "c" * 64,
            }
        ],
        "backtest_activity": {"items": []},
    }
    item = project_workflows(snapshot, now=NOW)["items"][0]
    assert item["state"] == "running"
    assert item["current_leaf"] is None
    assert item["native_backtest"] == {
        "state": "not_running",
        "basis": "no_live_leaf_run",
    }


def test_campaign_marks_native_backtest_running_only_from_live_execute_leaf():
    snapshot = {
        "alpha_campaigns": [
            {"id": "campaign-1", "status": "running", "phase": "campaign"}
        ],
        "backtest_activity": {
            "items": [
                {
                    "campaign_id": "campaign-1",
                    "task_id": "BT-009-7",
                    "status": "running",
                    "stage": "execute",
                    "heartbeat_at": "2026-10-22T11:59:30+00:00",
                    "progress": {"phase": "walk_forward"},
                }
            ]
        },
    }
    item = project_workflows(snapshot, now=NOW)["items"][0]
    assert item["native_backtest"]["state"] == "running"
    assert item["current_leaf"]["id"] == "BT-009-7"


def test_campaign_does_not_treat_terminal_receipt_as_live_leaf():
    snapshot = {
        "alpha_campaigns": [
            {"id": "campaign-1", "status": "running", "phase": "campaign"}
        ],
        "backtest_activity": {
            "items": [
                {
                    "campaign_id": "campaign-1",
                    "task_id": "BT-009-7",
                    "status": "succeeded",
                    "stage": "execute",
                    "execution_evidence": "native_terminal_receipt",
                }
            ]
        },
    }
    item = project_workflows(snapshot, now=NOW)["items"][0]
    assert item["native_backtest"]["state"] == "not_running"
