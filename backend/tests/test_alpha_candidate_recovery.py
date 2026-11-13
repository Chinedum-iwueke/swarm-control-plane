from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import UTC, datetime, timedelta

import pytest

from app.services.alpha_candidate_recovery import recovery_scope, matching_recovery, SCIENTIFIC_FIELDS


def fixture():
    data = {"venue":"bybit", "instruments":["BTCUSDT","SPXUSDT"], "research_timeframe":"4h",
            "liquidity_floor_usd":1000000, "required_fields":["close","quote_volume"]}
    document = {key:f"unchanged {key}" for key in SCIENTIFIC_FIELDS}
    document["data"] = data
    candidate = SimpleNamespace(id=uuid4(), cycle_id=uuid4(), candidate_digest="c"*64,
        question=document["question"], document=document, disposition="accepted")
    cycle = SimpleNamespace(mandate_id=uuid4())
    old = SimpleNamespace(specification={"bulletproof_source_commit":"a"*40})
    mandate = SimpleNamespace(specification={"bulletproof_source_commit":"b"*40})
    db = MagicMock()
    db.get.side_effect = lambda model,key: candidate if key==candidate.id else cycle if key==candidate.cycle_id else old
    db.scalar.return_value = None
    proposed = SimpleNamespace(**{key:document[key] for key in SCIENTIFIC_FIELDS},data=SimpleNamespace(**data))
    return db, mandate, candidate, proposed


def test_explicit_untested_source_recovery_preserves_identity():
    db, mandate, parent, candidate = fixture()
    before = deepcopy(parent.document)
    scope = recovery_scope(db,mandate,parent.id,parent.candidate_digest)
    cycle = SimpleNamespace(context={"founder_research_idea":{"constraints":{"retained_candidate_recovery":scope}}})
    assert matching_recovery(db,mandate,cycle,candidate)==scope
    assert scope["execution_authority"] is scope["novel_discovery"] is False
    assert parent.document==before
    assert matching_recovery(db,mandate,SimpleNamespace(context={}),candidate) is None


@pytest.mark.parametrize("fault",["digest","same_source","rejected","observed","inflight","question","target","criteria","basket","clock"])
def test_recovery_cannot_relabel_scientific_work_or_change_question(fault):
    db, mandate, parent, candidate = fixture()
    scope = recovery_scope(db,mandate,parent.id,parent.candidate_digest)
    if fault=="digest": parent.candidate_digest="d"*64
    elif fault=="same_source": mandate.specification["bulletproof_source_commit"]="a"*40
    elif fault=="rejected": parent.disposition="rejected"
    elif fault=="observed": db.scalar.side_effect=[uuid4(),None]
    elif fault=="inflight": db.scalar.side_effect=[None,uuid4()]
    elif fault=="question": candidate.question="different predictive question"
    elif fault=="target": candidate.target="direction not volatility"
    elif fault=="criteria": candidate.falsification_criteria=[]
    elif fault=="basket": candidate.data.instruments=["ETHUSDT"]
    else: candidate.data.research_timeframe="1h"
    cycle=SimpleNamespace(context={"founder_research_idea":{"constraints":{"retained_candidate_recovery":scope}}})
    with pytest.raises(ValueError): matching_recovery(db,mandate,cycle,candidate)


def test_novelty_gate_exempts_only_the_explicit_recovery_question(monkeypatch):
    from .test_alpha_discovery import candidate, DIGEST
    from app.services.alpha_discovery import _candidate_reasons
    from app.services import alpha_candidate_recovery as service
    value, object_id = candidate()
    cycle=SimpleNamespace(context={"research_intelligence":{"citations":[{"object_id":str(object_id),"content_digest":DIGEST}]},
        "datasets":[{"binding_index":0,"venue":"bybit","instruments":["BTCUSDT"],"timeframe":"1m","rows":10000,"output_columns":["timestamp","close","funding_rate","volume"]}]})
    mandate=SimpleNamespace(specification={"minimum_liquidity_usd":0})
    prior=[value.question]
    assert "duplicate_prior_question" in _candidate_reasons(value,cycle,mandate,prior)[0]
    monkeypatch.setattr(service,"matching_recovery",lambda *args:{"scientific_identity":{"question":value.question}})
    assert _candidate_reasons(value,cycle,mandate,prior)[0]==[]
    prior.append(value.question.replace("elevated", "extreme"))
    assert "semantic_duplicate_prior_question" in _candidate_reasons(value,cycle,mandate,prior)[0]


def test_duplicate_only_records_do_not_expand_the_novelty_exclusion_radius():
    from app.services.alpha_discovery import _candidate_enters_novelty_memory
    duplicate=SimpleNamespace(disposition="rejected",reason_codes=["semantic_duplicate_prior_question"])
    assert _candidate_enters_novelty_memory(duplicate) is False
    duplicate.reason_codes.append("scientific_requirement_invalid")
    assert _candidate_enters_novelty_memory(duplicate) is True


@pytest.mark.parametrize("stage", ["initial", "campaign", "terminal"])
def test_drain_pause_preserves_cycles_without_replenishing(monkeypatch, stage):
    from app.services import alpha_discovery as service
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(id=uuid4(), status="active", valid_until=moment + timedelta(days=1),
        cycle_count=1, hypothesis_count=0, trial_count=0,
        budget={"maximum_cycles":3,"maximum_hypotheses":3,"maximum_total_trials":24})
    cycle = None if stage == "initial" else SimpleNamespace(id=uuid4(),
        campaign_id=uuid4() if stage == "campaign" else None,
        status="running" if stage == "campaign" else "rejected",
        created_at=moment, completed_at=moment)
    db = MagicMock()
    db.scalar.return_value = cycle
    for name in ["_recover_premature_cycle_completion", "_retire_superseded_discovery_stalls", "_recover_resumed_stage"]:
        monkeypatch.setattr(service, name, lambda *_: None)
    monkeypatch.setattr(service, "_reconcile_campaign_cycles", lambda *_: {cycle.id} if cycle else set())
    monkeypatch.setattr(service, "_question_pipeline_state", lambda *_: (0, 0))
    monkeypatch.setattr(service, "_reconcile_data_admissions", lambda *_: False)
    monkeypatch.setattr(service, "_discovery_creation_paused", lambda *_: True)
    create = MagicMock()
    monkeypatch.setattr(service, "_new_cycle", create)
    service.reconcile_mandate(db, mandate)
    create.assert_not_called()
    assert mandate.cycle_count == 1


@pytest.mark.parametrize("scope_type,scope_key,expected", [
    ("global", "all", True), ("workflow", "autonomous-research", True),
    ("workflow", "unrelated", False), ("agent", "researcher", False),
])
def test_discovery_pause_scope_is_explicit(scope_type, scope_key, expected):
    from app.services.alpha_discovery import _discovery_creation_paused
    db = MagicMock()
    db.scalars.return_value.all.return_value = [SimpleNamespace(
        is_paused=True, scope_type=scope_type, scope_key=scope_key)]
    assert _discovery_creation_paused(db) is expected


def test_intake_can_be_staged_before_approval_without_executing(monkeypatch):
    from app.services import alpha_discovery as service
    from app.schemas.alpha_discovery import AlphaFounderResearchIdeaCreate
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(id=uuid4(), mandate_digest="a"*64, status="awaiting_approval",
        valid_from=moment-timedelta(hours=1),valid_until=moment+timedelta(days=1))
    db = MagicMock()
    existing = SimpleNamespace(status="queued")
    db.scalar.return_value = existing
    payload = AlphaFounderResearchIdeaCreate(mandate_id=mandate.id,
        expected_mandate_digest=mandate.mandate_digest, submitted_by="founder-operator",
        idea="Stage an unchanged research idea before mandate approval.")
    assert service.queue_founder_idea(db, mandate, payload) is existing
    monkeypatch.setattr(service, "_recover_premature_cycle_completion", lambda *_:None)
    create = MagicMock()
    monkeypatch.setattr(service, "_new_cycle", create)
    service.reconcile_mandate(db, mandate)
    create.assert_not_called()


@pytest.mark.parametrize("grounding", [
    {}, {"citations": [], "abstained": True, "error": "Projection stale"},
    {"citations": [{"object_id": "retained"}], "abstained": True},
])
def test_missing_grounding_consumes_no_cycle_or_model_task(monkeypatch, grounding):
    from app.services import alpha_discovery as service
    mandate = SimpleNamespace(id=uuid4(), cycle_count=1)
    idea = SimpleNamespace(status="queued", cycle_id=None)
    db = MagicMock()
    db.scalar.return_value = None
    event, task = MagicMock(), MagicMock()
    monkeypatch.setattr(service, "_event", event)
    monkeypatch.setattr(service, "_task", task)
    assert service._new_cycle(db, mandate, idea,
        prepared_context={"research_intelligence":grounding}) is None
    assert mandate.cycle_count == 1
    assert idea.status == "queued" and idea.cycle_id is None
    db.add.assert_not_called()
    task.assert_not_called()
    assert event.call_args.args[2] == "discovery_grounding_deferred"
    assert event.call_args.args[3]["cycle_budget_consumed"] is False
    db.scalar.return_value = uuid4()
    event.reset_mock()
    service._new_cycle(db, mandate, idea,prepared_context={"research_intelligence":grounding})
    event.assert_not_called()
