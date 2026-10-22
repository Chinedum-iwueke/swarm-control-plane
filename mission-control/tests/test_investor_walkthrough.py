from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_mission_control.investor_walkthrough import (
    WalkthroughJournal,
    project_investor_walkthrough,
)

NOW = datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc)


def _event(event_type: str, sequence: int, **overrides) -> dict:
    payload = {
        "event_id": f"event-{sequence}",
        "event_type": event_type,
        "venue": "bybit",
        "environment": "demo",
        "account_pseudonym": "acct-demo-7",
        "correlation_id": "trace-24",
        "client_order_id": "client-24",
        "venue_order_id": "venue-24",
        "execution_id": None,
        "observed_time": f"2026-10-22T17:59:{sequence:02d}+00:00",
        "evidence": {
            "event_digest": f"{sequence:x}" * 64,
            "receipt_digest": "a" * 64,
        },
    }
    payload.update(overrides)
    return payload


def _ready_inputs() -> tuple[dict, dict, dict]:
    snapshot = {
        "health": {"status": "ok"},
        "provenance": {
            "source_identity": "mission-control/dashboard",
            "generated_at": NOW.isoformat(),
        },
        "tasks": [{"id": "task-1", "assigned_agent_id": "agent-1"}],
        "agents": [{"id": "agent-1", "display_name": "Research executor"}],
        "backtest_activity": {
            "items": [
                {
                    "task_id": "bt-1",
                    "status": "succeeded",
                    "execution_evidence": "native_terminal_receipt",
                    "terminal_receipt": {"present": True, "digest": "b" * 64},
                    "artifacts": [{"id": "artifact-1", "sha256": "c" * 64}],
                    "ended_at": "2026-10-22T17:30:00+00:00",
                }
            ]
        },
    }
    workflows = {
        "items": [
            {
                "instance_id": "workflow-1",
                "state": "running",
                "updated_at": "2026-10-22T17:58:00+00:00",
                "current_leaf": {"id": "task-1"},
                "owner": {"type": "campaign", "id": "campaign-1"},
                "entry_evidence": {"digest": "d" * 64},
                "exit_evidence": {"digest": None},
            }
        ]
    }
    history = {
        "events": [
            _event("signal_decision", 1),
            _event("fill", 2, execution_id="fill-24"),
            _event("reconciliation", 3),
        ]
    }
    return snapshot, workflows, history


def test_walkthrough_selects_one_complete_canonical_chain():
    result = project_investor_walkthrough(*_ready_inputs(), now=NOW)

    assert result["status"] == "ready"
    assert result["ready_steps"] == result["total_steps"] == 5
    assert [step["id"] for step in result["steps"]] == [
        "command",
        "workflow",
        "agent",
        "backtest",
        "venue",
    ]
    assert result["steps"][1]["entity_id"] == "workflow-1"
    assert result["steps"][2]["entity_id"] == "agent-1"
    assert result["steps"][3]["evidence"][0]["kind"] == "bt009_terminal_receipt"
    assert result["steps"][4]["entity_id"] == "2" * 64


def test_walkthrough_discloses_missing_links_instead_of_substituting_activity():
    snapshot, workflows, history = _ready_inputs()
    snapshot["tasks"] = []
    snapshot["backtest_activity"] = {"items": [{"status": "succeeded"}]}
    history["events"] = [_event("fill", 2)]

    result = project_investor_walkthrough(snapshot, workflows, history, now=NOW)

    assert result["status"] == "incomplete"
    by_id = {step["id"]: step for step in result["steps"]}
    assert by_id["agent"]["status"] == "unavailable"
    assert "no canonically linked" in by_id["agent"]["unavailable_reason"]
    assert by_id["backtest"]["status"] == "unavailable"
    assert "task success is not substituted" in by_id["backtest"]["unavailable_reason"]
    assert by_id["venue"]["status"] == "unavailable"


def test_walkthrough_rejects_cross_account_event_correlation():
    snapshot, workflows, history = _ready_inputs()
    history["events"][-1]["account_pseudonym"] = "another-account"

    result = project_investor_walkthrough(snapshot, workflows, history, now=NOW)

    assert result["steps"][-1]["status"] == "unavailable"


def test_rehearsal_journal_retains_timing_findings_and_terminal_status(tmp_path):
    journal = WalkthroughJournal(tmp_path / "rehearsals.json", capacity=2)
    session = journal.start("a" * 64, 4, 5)
    observation = journal.observe(
        session["id"],
        {
            "step_id": "backtest",
            "kind": "evidence_gap",
            "elapsed_ms": 1200,
            "note": "The OOS receipt was unavailable.",
        },
    )
    finished = journal.finish(
        session["id"],
        status="completed",
        elapsed_ms=4200,
        summary="One disclosed evidence gap.",
    )

    assert observation["sequence"] == 1
    assert finished["status"] == "completed"
    assert finished["observations"][0]["kind"] == "evidence_gap"
    assert journal.path.stat().st_mode & 0o777 == 0o600
    assert journal.recent(1)[0]["summary"] == "One disclosed evidence gap."


def test_rehearsal_journal_rejects_unknown_or_terminal_session(tmp_path):
    journal = WalkthroughJournal(tmp_path / "rehearsals.json")
    with pytest.raises(KeyError):
        journal.observe("missing", {"step_id": "command"})
    session = journal.start("a" * 64, 5, 5)
    journal.finish(session["id"], status="abandoned", elapsed_ms=1, summary=None)
    with pytest.raises(ValueError, match="already terminal"):
        journal.observe(session["id"], {"step_id": "command"})
