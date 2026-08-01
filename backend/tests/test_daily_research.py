from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.models import ResearchDailyCycle
from app.schemas.research_program import ResearchProgramCreate
from app.services.daily_research import question_digest, reconcile_programs
from pydantic import ValidationError

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def program_payload() -> dict:
    return {
        "program_key": "M14-DAILY",
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
    db.scalars.side_effect = [SimpleNamespace(all=lambda: [program]), SimpleNamespace(all=list)]
    db.scalar.side_effect = [None, 0, 0]

    records = reconcile_programs(db, now=NOW)

    assert len(records) == 1
    assert records[0].status == "awaiting_brief"
    assert records[0].budget["max_trials_per_cycle"] == 1
    db.add.assert_called_once_with(records[0])


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
