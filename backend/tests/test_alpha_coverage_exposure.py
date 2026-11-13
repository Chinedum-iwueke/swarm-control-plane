from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.services.alpha_coverage_exposure import exposure_ledger, successor_context
from app.services.graph import digest_document as digest


def task(**changes):
    values = {
        "id": "t1",
        "plan_digest": "a" * 64,
        "status": "succeeded",
        "attempt_count": 1,
        "input_contract": {
            "stage": "execute",
            "campaign_id": "c1",
            "window_start": "2025-01-01T00:00:00Z",
            "window_end": "2026-01-01T00:00:00Z",
        },
        "result": {"summary": {"alpha_campaign_attempt": {"attempt_key": "attempt-1"}}},
    }
    return SimpleNamespace(**(values | changes))


def test_empty_audited_history_is_explicit_and_hashed():
    ledger = exposure_ledger([], [], lineage_digest="b" * 64)
    assert ledger["complete"] is True
    assert ledger["intervals"] == ledger["source_records"] == []
    assert ledger["ledger_digest"] == digest(
        {k: v for k, v in ledger.items() if k != "ledger_digest"}
    )


@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
def test_attempted_windows_are_excluded_regardless_of_outcome(status):
    ledger = exposure_ledger([task(status=status)], [], lineage_digest="b" * 64)
    assert ledger["intervals"] == [
        {"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"}
    ]


@pytest.mark.parametrize(
    "status", ["running", "leased", "queued", "pending_approval", "in_progress"]
)
def test_pending_execution_cannot_be_ignored(status):
    with pytest.raises(ValueError, match="pending or in flight"):
        exposure_ledger([task(status=status)], [], lineage_digest="b" * 64)


def test_unknown_window_fails_closed():
    with pytest.raises(ValueError, match="no reconstructible interval"):
        exposure_ledger(
            [task(input_contract={"stage": "execute"})], [], lineage_digest="b" * 64
        )


def test_every_scientific_attempt_needs_its_own_retained_contract():
    a = SimpleNamespace(
        id="a1", campaign_id="c1", attempt_key="attempt-1", trial_count=8
    )
    ledger = exposure_ledger([task()], [a], lineage_digest="b" * 64)
    assert len(ledger["attempt_records"]) == 1
    b = SimpleNamespace(
        id="a2", campaign_id="c1", attempt_key="missing-attempt", trial_count=8
    )
    with pytest.raises(ValueError, match="without retained exposure contracts"):
        exposure_ledger([task()], [a, b], lineage_digest="b" * 64)


def test_draft_and_compile_are_not_treated_as_executed_outcomes():
    assert (
        exposure_ledger(
            [
                task(input_contract={"stage": "draft"}),
                task(input_contract={"stage": "qualify"}),
            ],
            [],
            lineage_digest="b" * 64,
        )["intervals"]
        == []
    )


def test_legacy_mandate_gets_no_implicit_successor_authority():
    db = MagicMock()
    assert (
        successor_context(db, {}, {}, SimpleNamespace(specification={}), "a" * 40)
        is None
    )
    db.scalars.assert_not_called()
