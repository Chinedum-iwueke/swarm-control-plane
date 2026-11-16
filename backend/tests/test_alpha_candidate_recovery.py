from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import UTC, datetime, timedelta

import pytest

from app.services.alpha_candidate_recovery import recovery_scope, matching_recovery, SCIENTIFIC_FIELDS, apply_recovered_methods


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


def method_fixture(monkeypatch):
    from app.services.graph import digest_document
    from app.services import evaluator_routing
    db, mandate, parent, proposed = fixture()
    previous_get = db.get.side_effect
    cycle = previous_get(None, parent.cycle_id)
    cycle.campaign_id = uuid4()
    parent.document.update({
        "scientific_requirements": {
            "research_bar_minutes": 240, "feature_warmup_bars": 13,
            "minimum_training_bars": 1095, "minimum_validation_bars": 365,
            "minimum_test_bars": 365, "target_horizon_bars": 2,
            "purge_bars": 2, "embargo_bars": 2,
            "minimum_scientific_window_days": 365, "smoke_bars": 168,
            "minimum_event_support": {"heldout_events": 40},
            "rationale": "Prespecified support, not an observation of available events.",
        },
        "scientific_specification": {key: "Complete prespecified scientific method definition."
            for key in ("target_equation", "estimator", "threshold_rule", "control_rule",
                        "uncertainty_procedure", "split_and_update_policy", "missing_data_policy",
                        "event_support_rationale", "falsification_rule")},
        "parameter_budget": {"maximum_variants": 4},
        "representation_plan": {"candidate_key": "parent", "transformations": []},
    })
    card = {"source_candidate_document_digest": digest_document(parent.document)}
    subject = {"candidate_id": str(parent.id), "review_scope": "scientific_requirements",
               "source_commit": "a" * 40, "card_digest": digest_document(card),
               "artifact_bundle_digest": digest_document({})}
    digest = digest_document(subject)
    route = SimpleNamespace(id=uuid4(), subject_id=f"requirements:{parent.id}",
        subject_digest=digest, producer={"agent_id": str(uuid4())})
    event = SimpleNamespace(id=70854, campaign_id=cycle.campaign_id,
        event_type="scientific_requirements_published",
        payload={"subject": subject, "route_id": str(route.id),
                 "qualification": {"card": card, "artifact_bundle": {}}})
    db.get.side_effect = lambda model, key: event if key == event.id else route if key == route.id else previous_get(model, key)
    review = MagicMock(verdict="reject", blockers=["Split prose disagrees with native partition minima"])
    review.model_dump.return_value = {"verdict": "reject", "blockers": review.blockers}
    verifier = MagicMock(return_value=[review])
    monkeypatch.setattr(evaluator_routing, "validated_alpha_strategy_reviews", verifier)
    return db, mandate, parent, proposed, event, route, digest, verifier


@pytest.mark.parametrize("fault", [None, "missing_digest", "missing_candidate", "uuid_event"])
def test_method_correction_intake_binds_integer_publication_id(fault):
    from app.schemas.alpha_discovery import AlphaFounderResearchIdeaCreate
    payload = dict(mandate_id=uuid4(), expected_mandate_digest="a" * 64,
        idea="Correct an explicitly rejected scientific specification.", submitted_by="founder-operator",
        recovery_candidate_id=uuid4(), expected_recovery_candidate_digest="b" * 64,
        requirements_rejection_event_id=70854, expected_requirements_rejection_digest="c" * 64)
    if fault == "missing_digest": payload.pop("expected_requirements_rejection_digest")
    elif fault == "missing_candidate":
        payload.pop("recovery_candidate_id")
        payload.pop("expected_recovery_candidate_digest")
    elif fault == "uuid_event": payload["requirements_rejection_event_id"] = uuid4()
    if fault:
        with pytest.raises(ValueError): AlphaFounderResearchIdeaCreate.model_validate(payload)
    else:
        assert AlphaFounderResearchIdeaCreate.model_validate(payload).requirements_rejection_event_id == 70854


def test_method_correction_requires_rejection_and_preserves_history(monkeypatch):
    db, mandate, parent, proposed, event, route, digest, verifier = method_fixture(monkeypatch)
    mandate.specification["bulletproof_source_commit"] = "a" * 40
    before = deepcopy(parent.document)
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest, schema_version=3,
                           rejection_event_id=event.id, expected_rejection_digest=digest)
    cycle = SimpleNamespace(context={"founder_research_idea": {"constraints": {"retained_candidate_recovery": scope}}})
    assert matching_recovery(db, mandate, cycle, proposed) == scope
    revised = deepcopy(before)
    revised["candidate_key"] = "new"
    revised["representation_plan"]["candidate_key"] = "new"
    with pytest.raises(ValueError, match="must change"):
        apply_recovered_methods(revised, scope)
    revised["scientific_specification"]["split_and_update_policy"] = "Fixed minima of 1095/365/365, not percentage allocations."
    audit = apply_recovered_methods(revised, scope)
    assert audit["execution_authority"] is False
    assert audit["requires_fresh_independent_review"] is True
    assert parent.document == before
    verifier.assert_called()


@pytest.mark.parametrize("fault", ["candidate", "campaign", "route", "digest", "unverified", "approved", "observed", "card", "bundle"])
def test_method_correction_rejects_wrong_or_unverified_evidence(monkeypatch, fault):
    db, mandate, parent, proposed, event, route, digest, verifier = method_fixture(monkeypatch)
    if fault == "candidate": event.payload["subject"]["candidate_id"] = str(uuid4())
    elif fault == "campaign": event.campaign_id = uuid4()
    elif fault == "route": route.subject_id = "requirements:another-candidate"
    elif fault == "digest": digest = "f" * 64
    elif fault == "unverified": verifier.return_value = None
    elif fault == "approved": verifier.return_value[0].verdict = "approve"
    elif fault == "card": event.payload["qualification"]["card"]["source_candidate_document_digest"] = "f" * 64
    elif fault == "bundle": event.payload["qualification"]["artifact_bundle"]["changed"] = True
    else: db.scalar.return_value = uuid4()
    with pytest.raises(ValueError):
        recovery_scope(db, mandate, parent.id, parent.candidate_digest, schema_version=3,
                       rejection_event_id=event.id, expected_rejection_digest=digest)


@pytest.mark.parametrize("fault", ["bars", "events", "clock", "horizon", "variants", "question"])
def test_method_correction_cannot_weaken_constraints(monkeypatch, fault):
    db, mandate, parent, proposed, event, route, digest, verifier = method_fixture(monkeypatch)
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest, schema_version=3,
                           rejection_event_id=event.id, expected_rejection_digest=digest)
    revised = deepcopy(parent.document)
    revised["candidate_key"] = "new"
    if fault == "bars": revised["scientific_requirements"]["minimum_test_bars"] = 364
    elif fault == "events": revised["scientific_requirements"]["minimum_event_support"] = {}
    elif fault == "clock": revised["scientific_requirements"]["research_bar_minutes"] = 60
    elif fault == "horizon": revised["scientific_requirements"]["target_horizon_bars"] = 1
    elif fault == "variants": revised["parameter_budget"]["maximum_variants"] = 8
    else: revised["question"] = "A different question"
    with pytest.raises(ValueError):
        apply_recovered_methods(revised, scope)


def test_event_support_feedback_names_exact_missing_contract_keys(monkeypatch):
    db, mandate, parent, proposed, event, route, digest, verifier = method_fixture(monkeypatch)
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest, schema_version=3,
                           rejection_event_id=event.id, expected_rejection_digest=digest)
    revised = deepcopy(parent.document)
    revised["scientific_requirements"]["minimum_event_support"] = {"renamed_events": 40}
    with pytest.raises(ValueError) as error:
        apply_recovered_methods(revised, scope)
    assert '"heldout_events": {"proposed_minimum": null, "required_minimum": 40}' in str(error.value)


def test_source_recovery_reuses_methods_without_rewriting_parent_or_claiming_review():
    db, mandate, parent, proposed = fixture()
    parent.document.update({
        "scientific_requirements": {"minimum_test_bars": 548},
        "scientific_specification": {"split_and_update_policy": "frozen 60/20/20"},
        "representation_plan": {"candidate_key": "parent", "transformations": [{"operation": "log_return"}]},
        "parameter_budget": {"maximum_variants": 4},
    })
    before = deepcopy(parent.document)
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest)
    raw = {"question": parent.question, "candidate_key": "successor",
           "scientific_requirements": {"minimum_test_bars": 365},
           "scientific_specification": {"split_and_update_policy": "changed"}}
    audit = apply_recovered_methods(raw, scope)
    assert raw["scientific_requirements"] == before["scientific_requirements"]
    assert raw["scientific_specification"] == before["scientific_specification"]
    assert raw["representation_plan"]["candidate_key"] == "successor"
    assert audit["requires_fresh_independent_review"] is True
    assert audit["execution_authority"] is False
    assert parent.document == before
    raw["scientific_requirements"]["minimum_test_bars"] = 1
    assert scope["method_identity"]["scientific_requirements"]["minimum_test_bars"] == 548


def test_legacy_recovery_scope_remains_immutable():
    db, mandate, parent, candidate = fixture()
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest, schema_version=1)
    assert "schema_version" not in scope and "method_identity" not in scope
    cycle = SimpleNamespace(context={"founder_research_idea": {"constraints": {"retained_candidate_recovery": scope}}})
    assert matching_recovery(db, mandate, cycle, candidate) == scope
    raw = {"question": parent.question, "scientific_requirements": {"minimum_test_bars": 365}}
    before = deepcopy(raw)
    assert apply_recovered_methods(raw, scope) == {}
    assert raw == before


def test_recovered_methods_cannot_be_attached_to_an_unrelated_question():
    db, mandate, parent, candidate = fixture()
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest)
    with pytest.raises(ValueError, match="another question"):
        apply_recovered_methods({"question": "different scientific question"}, scope)


@pytest.mark.parametrize("fault", [None, "missing", "extra", "foreign"])
def test_native_qualified_columns_preserve_exact_per_asset_requirements(fault):
    db, mandate, parent, candidate = fixture()
    scope = recovery_scope(db, mandate, parent.id, parent.candidate_digest)
    candidate.data.required_fields = [f"{asset}__{field}" for asset in candidate.data.instruments
                                      for field in ["close", "quote_volume"]]
    if fault == "missing": candidate.data.required_fields.pop()
    if fault == "extra": candidate.data.required_fields.append("BTCUSDT__funding_rate")
    if fault == "foreign": candidate.data.required_fields.append("ETHUSDT__close")
    cycle = SimpleNamespace(context={"founder_research_idea":{"constraints":{"retained_candidate_recovery":scope}}})
    if fault:
        with pytest.raises(ValueError): matching_recovery(db, mandate, cycle, candidate)
    else:
        assert matching_recovery(db, mandate, cycle, candidate) == scope


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
