from datetime import datetime, UTC
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from app.services.alpha_candidate_blockers import project, overview


def campaign():
    return NS(id=uuid4(), campaign_key="commissioning", hypothesis_count=1,
              specification={"research_queue": [{"question": "old question", "source_candidate_id": str(uuid4())},
                                                {"question": "current question", "source_candidate_id": str(uuid4())}]},
              heartbeat_at=datetime.now(UTC), next_action="scientific_requirements_rejected",
              terminal_reason={"category": "scientific_requirements_rejected"})


def test_deferral_survives_campaign_advancement():
    c = campaign()
    a = NS(id=uuid4(), source_candidate_id=uuid4(), question="SONIC question",
           gate_report={"failed_gates": ["produce_admitted_predictor_coverage", "Obtain coverage"]},
           evidence_digests=["a" * 64], trial_count=0, created_at=datetime.now(UTC))
    event = NS(payload={"reason": "produce_admitted_predictor_coverage", "retry_condition": "Reviewed successor", "detail": {"fields": ["basis", "open_interest"]}})
    result = project(c, a, event)
    assert result["question"] == "SONIC question"
    assert result["status"] == "deferred"
    assert result["retry_condition"] == "Reviewed successor"
    assert result["detail"]["fields"] == ["basis", "open_interest"]
    assert result["scientific_result"] is False
    assert result["responsible_component"] == "Native data admission"


def test_current_blocker_is_separate_and_unknown_owner_is_not_invented():
    c = campaign()
    assert project(c)["question"] == "current question"
    c.next_action = "unknown"
    c.terminal_reason = {}
    assert project(c)["responsible_component"] == "Not recorded"
    c.hypothesis_count = 2
    assert project(c) is None


def test_filters_and_paging_are_database_bounded():
    db = MagicMock()
    db.scalar.return_value = 0
    db.execute.return_value.mappings.return_value.all.return_value = []
    result = overview(db, category="deferred", query="BTC%", offset=25, limit=25)
    statement = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "UNION ALL" in str(statement)
    assert "LIMIT" in str(statement) and "OFFSET" in str(statement)
    assert "BTC/%" in statement.params.values()
    assert result["items"] == [] and result["has_more"] is False
    db.get.assert_not_called()
