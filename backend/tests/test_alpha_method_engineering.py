from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.proposal import ProposalEngineeringMissionContract
from app.services.alpha_method_engineering import bound_engineering_contract, verified_plan_evidence
from app.services.graph import digest_document as digest


def fixture():
    source = 'a'*40
    template = ProposalEngineeringMissionContract(repository='bulletproof_bt', workflow='engineering-mission',
        base_ref=source, milestone_id='AEP-007', work_item_id='example',
        objective='Implement the exact reviewed signal specification.',
        allowed_paths=['src/bt/strategy'], acceptance_criteria=['Exact signal'],
        stop_conditions=['No authority expansion'], max_files_changed=2, max_diff_lines=100,
        max_duration_seconds=600, engineering_episode={'focused_tests': ['tests/test_example.py']})
    plans = {}
    for mode in ('smoke', 'scientific'):
        plan = dict(schema_version='requirements-aware-validation-plan-v1', mode=mode, source_commit=source,
                    status='ready', reasons=[], partitions={'test': {'start': '2025-01-01', 'end': '2025-02-01'}},
                    execution_authority=False)
        plans[mode] = plan | {'plan_digest': digest(plan)}
    report = {'validation_plans': plans}
    packet = dict(source_commit=source, requirements={'target': 'exact'},
                  evidence={digest(report): report}, proposal={'method': {'estimand': 'exact'}})
    identities = {kind: dict(agent_id=kind, profile_digest='b'*64, context_group=kind)
                  for kind in ('strategy_spec', 'causality_leakage')}
    reviews = {kind: dict(identity=identity, verdict=dict(packet_digest=digest(packet), verdict='accept',
                  checks=['target'], findings=[], rationale='Synthetic fixture only.'))
               for kind, identity in identities.items()}
    producers = [dict(agent_id='producer', profile_digest='c'*64, context_group='producer')]
    return template, packet, identities, reviews, producers, digest(report)


def test_backend_handoff_passes_exact_worker_verifier_without_rewriting_template(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.policy import EngineeringMissionContract
    from swarm_worker.accepted_method_handoff import verify_handoff
    template, packet, identities, reviews, producers, plan_digest = fixture()
    original = deepcopy(template.model_dump(mode='json'))
    bound = bound_engineering_contract(template, packet=packet, reviews=reviews, identities=identities,
        producers=producers, registration_receipt={'route_id': 'synthetic-only'},
        plan_evidence_digest=plan_digest)
    worker = EngineeringMissionContract.model_validate(bound.model_dump(mode='json'))
    assert verify_handoff(worker, template.base_ref)['execution_authority'] is False
    assert template.model_dump(mode='json') == original
    with pytest.raises(ValueError, match='rebind'):
        bound_engineering_contract(bound, packet=packet, reviews=reviews, identities=identities,
            producers=producers, registration_receipt={'route_id': 'synthetic-only'},
            plan_evidence_digest=plan_digest)


@pytest.mark.parametrize('state', ['queued', 'failed', 'cancelled'])
def test_native_plan_custody_cannot_use_unfinished_tasks(state):
    template, packet, *_ = fixture()
    request = SimpleNamespace(feasibility_task_id=uuid4(), contract=template)
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status=state)
    with pytest.raises(ValueError, match='successful native planning'):
        verified_plan_evidence(db, request, packet, SimpleNamespace())


def test_scheduler_materializes_once_and_retains_engineering_approval(monkeypatch):
    from app.services import alpha_method_engineering as module, alpha_method_tasks, evaluator_routing
    from app.schemas.alpha_campaign import MethodEngineeringRequest
    template, packet, identities, reviews, producers, plan_digest = fixture()
    candidate = str(uuid4())
    method = SimpleNamespace(id=uuid4(), input_contract={'candidate_id': candidate})
    request = MethodEngineeringRequest(contract=template, feasibility_task_id=uuid4(),
                                       plan_evidence_digest=plan_digest).model_dump(mode='json')
    campaign = SimpleNamespace(id=uuid4(), campaign_digest='e'*64,
                              specification={'method_engineering_requests': {candidate: request}})
    route = SimpleNamespace(id=uuid4())
    assignments, profiles, events = [], {}, []
    for kind, identity in identities.items():
        profile_id = uuid4()
        profiles[profile_id] = identity
        assignments.append(SimpleNamespace(evaluator_profile_id=profile_id, review_kind=kind,
                                           assignment_digest=kind, review_digest=kind))
        events.append(SimpleNamespace(payload={'assignment_digest': kind, 'review_digest': kind,
                                               'alpha_strategy_review': {'method_verdict': reviews[kind]['verdict']}}))
    monkeypatch.setattr(alpha_method_tasks, 'require_current_method_authority', lambda *_: None)
    monkeypatch.setattr(module, 'verified_plan_evidence', lambda *_: None)
    monkeypatch.setattr(alpha_method_tasks, 'route_method_review',
                        lambda *_: (route, [SimpleNamespace(verdict='approve')]*2))
    monkeypatch.setattr(evaluator_routing, 'require_independence',
                        lambda *_: SimpleNamespace(receipt_digest='d'*64))
    monkeypatch.setattr(evaluator_routing, '_profile_identity', lambda p: p)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: producers[0])
    saved = MagicMock()
    monkeypatch.setattr(module, 'persist_new_task', saved)
    db = MagicMock()
    db.get.side_effect = lambda _, key: profiles.get(key)
    db.scalar.return_value = None
    db.scalars.return_value.all.side_effect = [assignments, events, assignments, events]
    created = module.materialize_method_engineering(db, campaign, method, packet, producers[0], route, request)
    assert created.approval_required is True
    assert created.parent_task_id == method.id
    assert created.task_type == 'engineering_mission'
    db.scalar.return_value = created
    assert module.materialize_method_engineering(db, campaign, method, packet, producers[0], route, request) is created
    saved.assert_called_once()
    assert campaign.specification['method_engineering_requests'][candidate] == request
