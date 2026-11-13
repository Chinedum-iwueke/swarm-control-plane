from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

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
