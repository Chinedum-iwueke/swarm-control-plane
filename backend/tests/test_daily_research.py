from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.models import ResearchDailyCycle, ResearchDataSnapshot
from app.schemas.research_program import ResearchCycleApproval, ResearchProgramCreate
from app.services.daily_research import (
    decide_cycle,
    question_digest,
    rank_daily_candidates,
    reconcile_programs,
)
from fastapi import HTTPException
from pydantic import ValidationError

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def program_payload() -> dict:
    return {
        "program_key": "M14-DAILY",
        "project": "bulletproof-bt",
        "title": "Daily supervised research",
        "mandate": [
            {
                "question_key": "funding-extremes",
                "question": "Do funding-rate extremes predict residual BTC returns?",
                "rationale": "Funding pressure may proxy crowded directional positioning.",
                "source": "founder_priority",
                "tags": ["funding", "btc"],
            }
        ],
        "schedule": {"weekdays_utc": [0, 1, 2, 3, 4], "hour_utc": 8},
        "budget": {
            "max_cycles_per_week": 5,
            "max_trials_per_cycle": 1,
            "max_compute_seconds_per_cycle": 1800,
        },
        "created_by": "founder-operator",
    }


def test_program_contract_rejects_duplicate_days_and_question_keys() -> None:
    payload = program_payload()
    payload["schedule"]["weekdays_utc"] = [0, 0]
    with pytest.raises(ValidationError, match="weekdays must be unique"):
        ResearchProgramCreate.model_validate(payload)

    payload = program_payload()
    payload["mandate"].append(payload["mandate"][0])
    with pytest.raises(ValidationError, match="question keys must be unique"):
        ResearchProgramCreate.model_validate(payload)


def test_question_digest_is_case_and_punctuation_stable() -> None:
    assert question_digest("Does BTC predict returns?") == question_digest(
        "  DOES btc predict returns  "
    )


def test_daily_cycle_and_snapshot_orm_columns_do_not_overlap() -> None:
    cycle_columns = set(ResearchDailyCycle.__table__.columns.keys())
    snapshot_columns = set(ResearchDataSnapshot.__table__.columns.keys())

    assert "snapshot_key" not in cycle_columns
    assert "content_digest" not in cycle_columns
    assert "question_digest" not in snapshot_columns
    assert "snapshot_key" in snapshot_columns


def test_reconcile_creates_only_one_budgeted_daily_cycle() -> None:
    payload = ResearchProgramCreate.model_validate(program_payload())
    program = SimpleNamespace(
        id=uuid4(),
        mandate=[item.model_dump(mode="json") for item in payload.mandate],
        schedule=payload.schedule.model_dump(mode="json"),
        budget=payload.budget.model_dump(mode="json"),
        created_at=NOW,
    )
    db = MagicMock()
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [program]),
        SimpleNamespace(all=list),
    ]
    db.scalar.side_effect = [None, 0, 0]

    records = reconcile_programs(db, now=NOW)

    assert len(records) == 1
    assert records[0].status == "awaiting_brief"
    assert records[0].budget["max_trials_per_cycle"] == 1
    assert records[0].digest["selection"] == {
        "schema_version": "daily-research-selection-v1.0.0",
        "mode": "static_fallback",
        "reason": "no_approved_current_novel_candidate",
        "candidate_count": 0,
    }
    assert db.add.call_count == 2


def test_reconcile_respects_weekly_cycle_budget() -> None:
    payload = ResearchProgramCreate.model_validate(program_payload())
    program = SimpleNamespace(
        id=uuid4(),
        mandate=[item.model_dump(mode="json") for item in payload.mandate],
        schedule=payload.schedule.model_dump(mode="json"),
        budget=payload.budget.model_dump(mode="json"),
        created_at=NOW,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [program]
    db.scalar.side_effect = [None, payload.budget.max_cycles_per_week]

    assert reconcile_programs(db, now=NOW) == []
    db.add.assert_not_called()


def test_reconcile_adopts_unapproved_legacy_cycle_after_deployment() -> None:
    payload = ResearchProgramCreate.model_validate(program_payload())
    program = SimpleNamespace(
        id=uuid4(),
        mandate=[item.model_dump(mode="json") for item in payload.mandate],
        schedule=payload.schedule.model_dump(mode="json"),
        budget=payload.budget.model_dump(mode="json"),
        created_at=NOW,
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        status="awaiting_brief",
        digest={"source": "founder_priority"},
        question_digest="a" * 64,
        task_id=None,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [program]
    db.scalar.return_value = cycle

    assert reconcile_programs(db, now=NOW) == [cycle]
    assert cycle.digest["selection"]["reason"] == (
        "legacy_cycle_adopted_after_director_deployment"
    )
    event = db.add.call_args.args[0]
    assert event.event_type == "proposal_created"
    assert event.detail["execution_authority"] is False


def test_reconcile_marks_exact_prior_question_as_duplicate() -> None:
    payload = ResearchProgramCreate.model_validate(program_payload())
    program = SimpleNamespace(
        id=uuid4(),
        mandate=[item.model_dump(mode="json") for item in payload.mandate],
        schedule=payload.schedule.model_dump(mode="json"),
        budget=payload.budget.model_dump(mode="json"),
        created_at=NOW,
    )
    prior = SimpleNamespace(
        id=uuid4(),
        specification={"research_question": payload.mandate[0].question},
    )
    db = MagicMock()
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [program]),
        SimpleNamespace(all=lambda: [prior]),
    ]
    db.scalar.side_effect = [None, 0, 0]

    cycle = reconcile_programs(db, now=NOW)[0]

    assert isinstance(cycle, ResearchDailyCycle)
    assert cycle.status == "duplicate_avoided"
    assert cycle.duplicate_hypothesis_id == prior.id
    assert cycle.completed_at == NOW


def test_director_ranks_current_approved_candidates_deterministically() -> None:
    candidates = [
        {
            "publication_id": "b",
            "question": "Does a novel execution signal improve BTC outcomes?",
            "priority_score": 0.8,
            "novelty_score": 0.9,
            "evidence_quality": 0.8,
            "publication_status": "published",
            "created_at": NOW - timedelta(days=1),
        },
        {
            "publication_id": "a",
            "question": "Does another execution signal improve BTC outcomes?",
            "priority_score": 0.8,
            "novelty_score": 0.9,
            "evidence_quality": 0.8,
            "publication_status": "published",
            "created_at": NOW - timedelta(days=1),
        },
    ]
    first = rank_daily_candidates(candidates, [], now=NOW)
    second = rank_daily_candidates(list(reversed(candidates)), [], now=NOW)
    assert [item["publication_id"] for item in first] == [
        item["publication_id"] for item in second
    ]


def test_director_excludes_stale_retracted_and_duplicate_families() -> None:
    candidates = [
        {
            "publication_id": "stale",
            "question": "Does stale funding evidence predict BTC returns?",
            "priority_score": 1.0,
            "novelty_score": 1.0,
            "evidence_quality": 1.0,
            "publication_status": "published",
            "created_at": NOW - timedelta(days=31),
        },
        {
            "publication_id": "retracted",
            "question": "Does retracted evidence predict BTC returns?",
            "priority_score": 1.0,
            "novelty_score": 1.0,
            "evidence_quality": 1.0,
            "publication_status": "retracted",
            "created_at": NOW,
        },
        {
            "publication_id": "duplicate",
            "question": "Do funding extremes predict BTC residual returns?",
            "priority_score": 1.0,
            "novelty_score": 1.0,
            "evidence_quality": 1.0,
            "publication_status": "published",
            "created_at": NOW,
        },
    ]
    assert (
        rank_daily_candidates(
            candidates,
            ["Do funding extremes predict BTC residual returns?"],
            now=NOW,
        )
        == []
    )


def test_founder_decision_emits_task_ready_without_execution_authority() -> None:
    cycle = SimpleNamespace(
        id=uuid4(),
        status="awaiting_brief",
        question_digest="a" * 64,
        digest={"selection": {"schema_version": "daily-research-selection-v1.0.0"}},
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    decided = decide_cycle(
        db,
        cycle,
        ResearchCycleApproval(
            expected_question_digest="a" * 64,
            decision="approved",
            rationale="The evidence provenance and bounded research budget are acceptable.",
            decided_by="founder-operator",
        ),
    )

    assert decided.digest["approval"]["decision"] == "approved"
    events = [call.args[0] for call in db.add.call_args_list]
    assert [event.event_type for event in events] == ["approved", "task_ready"]
    assert events[-1].detail["approval_required_for_execution"] is True
    db.commit.assert_called_once()


def test_founder_decision_rejects_digest_race() -> None:
    cycle = SimpleNamespace(
        id=uuid4(),
        status="awaiting_brief",
        question_digest="a" * 64,
        digest={},
    )
    with pytest.raises(HTTPException, match="digest changed"):
        decide_cycle(
            MagicMock(),
            cycle,
            ResearchCycleApproval(
                expected_question_digest="b" * 64,
                decision="approved",
                rationale="This stale approval must not apply to a changed question.",
                decided_by="founder-operator",
            ),
        )
