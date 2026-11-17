from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.method_task import MethodTaskContract
from app.services import alpha_method_tasks as service


def fixture():
    now = datetime.now(timezone.utc)
    candidate, mandate_id = uuid4(), uuid4()
    evidence = {'kind': 'synthetic_assumption'}
    request = MethodTaskContract.model_validate(dict(repository='bulletproof_bt',
        workflow='alpha-method-design', base_ref='a'*40, candidate_id=str(candidate),
        candidate_digest='b'*64, mandate_id=str(mandate_id), mandate_digest='c'*64,
        valid_until=(now+timedelta(hours=1)).isoformat(),
        proposal={'scientific_identity': {'question': 'frozen'}, 'support_minima': {'rows': 100},
                  'method': {'schema_version': 'design-adequacy-contract-v1', 'estimand': 'contrast'}},
        requirements={'target': 'Retain the exact target'},
        evidence_catalog={service.digest(evidence): evidence}, dependencies={'coverage': 'd'*64},
        findings_digest='e'*64, policy={'allowed_method_fields': ['estimator_id']},
        diagnostic='design_adequacy_v1', authority='method_design_no_execution')).model_dump(mode='json')
    source = {'source_candidate_id': str(candidate), 'source_candidate_digest': 'b'*64, 'rank': 1}
    campaign = SimpleNamespace(id=uuid4(), status='running', campaign_digest='f'*64,
        activated_at=now, budget={'max_duration_seconds': 7200},
        specification={'research_mandate_id': str(mandate_id), 'research_mandate_digest': 'c'*64,
            'bulletproof_source_commit': 'a'*40, 'method_design_requests': {str(candidate): request}})
    mandate = SimpleNamespace(status='active', mandate_digest='c'*64,
        valid_from=now-timedelta(hours=1), valid_until=now+timedelta(hours=2),
        specification={'bulletproof_source_commit': 'a'*40})
    parent = SimpleNamespace(id=uuid4(), status='succeeded')
    activation = SimpleNamespace(payload={'campaign_digest': campaign.campaign_digest})
    db = MagicMock()
    db.get.return_value = mandate
    db.scalar.side_effect = [activation, None]
    return db, campaign, source, parent, request, mandate, activation


def test_method_task_materialization_reuses_exact_task_and_preserves_budget(monkeypatch):
    db, campaign, source, parent, request, _, activation = fixture()
    saved = MagicMock()
    monkeypatch.setattr(service, 'persist_new_task', saved)
    before = deepcopy(campaign.specification)
    task = service.materialize_method_task(db, campaign, source, parent, request)
    assert task.task_type == 'alpha_method_design'
    assert task.required_capabilities == ['alpha-method-design']
    assert task.parent_task_id == parent.id
    assert task.approval_required is False
    db.scalar.side_effect = [activation, task]
    assert service.materialize_method_task(db, campaign, source, parent, request) is task
    saved.assert_called_once()
    assert campaign.specification == before


@pytest.mark.parametrize('change', ['expired', 'revoked', 'source', 'candidate', 'request', 'activation'])
def test_method_task_rejects_changed_or_unapproved_authority(monkeypatch, change):
    db, campaign, source, parent, request, mandate, _ = fixture()
    saved = MagicMock()
    monkeypatch.setattr(service, 'persist_new_task', saved)
    request = deepcopy(request)
    if change == 'expired':
        mandate.valid_until = datetime.now(timezone.utc)-timedelta(seconds=1)
    elif change == 'revoked':
        mandate.status = 'revoked'
    elif change == 'source':
        mandate.specification['bulletproof_source_commit'] = '0'*40
    elif change == 'candidate':
        source['source_candidate_digest'] = '0'*64
    elif change == 'request':
        request['policy']['max_repairs'] = 3
    else:
        db.scalar.side_effect = [None]
    with pytest.raises(ValueError):
        service.materialize_method_task(db, campaign, source, parent, request)
    saved.assert_not_called()


def test_method_schema_matches_worker_normalization(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    request = fixture()[4]
    assert WorkerContract.model_validate(request).model_dump(mode='json') == request
    for model in (WorkerContract, MethodTaskContract):
        changed = deepcopy(request)
        changed['policy']['allowed_method_fields'] = ['estimand']
        with pytest.raises(ValueError):
            model.model_validate(changed)


def test_cached_method_authority_is_checked_again():
    db, campaign, _, _, request, mandate, _ = fixture()
    db.scalar.side_effect = None
    db.scalar.return_value = campaign
    task = SimpleNamespace(id=uuid4(), task_type='alpha_method_design', input_contract=request,
                           approval_policy={'campaign_digest': campaign.campaign_digest})
    service.require_current_method_authority(db, task)
    mandate.status = 'revoked'
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match='authority'):
        service.require_current_method_authority(db, task)
    mandate.status = 'active'
    campaign.status = 'cancelled'
    with pytest.raises(HTTPException, match='authority'):
        service.require_current_method_authority(db, task)


def ready_task():
    raw = fixture()[4]
    c = MethodTaskContract.model_validate(raw)
    task = SimpleNamespace(id=uuid4(), status='succeeded', input_contract=raw,
                           started_at=datetime.now(timezone.utc))
    request = dict(schema_version='native-diagnostic-request-v1', tool=c.diagnostic,
        source_commit=c.base_ref, subject_digest=service.digest(c.proposal), payload=c.proposal['method'])
    receipt = dict(schema_version='native-diagnostic-receipt-v1', tool=c.diagnostic,
        request_digest=service.digest(request), source_commit=c.base_ref,
        subject_digest=service.digest(c.proposal), evidence_catalog_digest=service.digest(c.evidence_catalog),
        execution_authority=False, scientific_certification=False, market_data_used=False,
        implementation_digests={'fixture': '0'*64}, evidence_kind='design_diagnostic',
        result={'status': 'requires_independent_review_and_native_calibration',
                'contract_digest': service.digest(c.proposal['method'])})
    receipt['receipt_digest'] = service.digest(receipt)
    state = dict(binding=dict(task_id=str(task.id), source_commit=c.base_ref,
        mandate_digest=c.mandate_digest, findings_digest=c.findings_digest,
        contract_digest=service.digest(raw), kind='method-episode-v1',
        initial_digest=service.digest(c.proposal), policy=c.policy.model_dump()),
        proposal=c.proposal, scientific_approval=False, execution_authority=False,
        model_calls=0, repairs=0, tool_calls=1, reserved_work=c.policy.tool_work_limit,
        deadline=task.started_at.timestamp() + c.policy.max_duration_seconds,
        status='ready_for_independent_review', evidence={service.digest(receipt): receipt})
    packet = dict(schema_version='method-review-packet-v1', method_episode_digest=service.digest(state),
        source_commit=c.base_ref, proposal=state['proposal'], requirements=c.requirements,
        dependencies=c.dependencies, evidence=state['evidence'], prior_requirements={})
    result = dict(schema_version='method-task-result-v1', contract_digest=service.digest(raw),
        state=state, review_packet=packet, scientific_approval=False, execution_authority=False)
    result['result_digest'] = service.digest(result)
    task.result = {'summary': {'method_episode': deepcopy(result)}}
    return task


def test_exact_method_result_verifies_but_not_scientific_acceptance():
    task = ready_task()
    result = service.verified_method_result(task)
    assert result['scientific_approval'] is False
    assert result['execution_authority'] is False


@pytest.mark.parametrize('change', ['identity', 'scope', 'budget', 'source', 'receipt'])
def test_rehashed_invalid_method_state_cannot_publish(change):
    task = ready_task()
    result = task.result['summary']['method_episode']
    if change == 'identity':
        result['state']['proposal']['scientific_identity'] = {'question': 'different'}
    elif change == 'scope':
        result['state']['proposal']['method']['estimand'] = 'different'
    elif change == 'budget':
        result['state']['model_calls'] = 999
    elif change == 'source':
        result['state']['binding']['source_commit'] = '0'*40
    else:
        result['review_packet']['evidence'] = {}
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    with pytest.raises(ValueError):
        service.verified_method_result(task)


def test_campaign_dispatches_explicit_method_request_before_engineering(monkeypatch):
    from app.services import alpha_campaign
    db, campaign, source, parent, request, _, _ = fixture()
    campaign.specification.update(execution_protocol='alpha003-governed-v1', research_queue=[source])
    campaign.hypothesis_count = 0
    db.scalar.side_effect = [parent]
    dispatch = MagicMock(return_value=SimpleNamespace(status='queued'))
    monkeypatch.setattr(service, 'advance_method_task', dispatch)
    legacy = MagicMock(side_effect=AssertionError('must not bypass method review'))
    monkeypatch.setattr(alpha_campaign, '_create_strategy_engineering_task', legacy)
    result = alpha_campaign._advance_governed_pipeline_ready(db, campaign)
    assert result.status == 'queued'
    dispatch.assert_called_once_with(db, campaign, source, parent, request)
    legacy.assert_not_called()


def test_ready_packet_publication_is_idempotent_and_stops_before_engineering(monkeypatch):
    from app.services import alpha_campaign, evaluator_routing
    from app.services import alpha_method_recovery
    monkeypatch.setattr(alpha_method_recovery, 'recorded_successor', lambda *_: None)
    db, campaign, source, parent, request, _, _ = fixture()
    task = ready_task()
    task.plan_digest = '1'*64
    monkeypatch.setattr(service, 'materialize_method_task', lambda *_: task)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: {'agent_id': 'producer'})
    monkeypatch.setattr(service, 'route_method_review', lambda *_: (SimpleNamespace(status='assigned'), None))
    published = []
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: published.append(args[-1]))
    db.scalar.side_effect = [None]
    assert service.advance_method_task(db, campaign, source, parent, request) is None
    assert campaign.next_action == 'await_independent_method_review'
    assert len(published) == 1
    db.scalar.side_effect = [SimpleNamespace(payload=published[0])]
    assert service.advance_method_task(db, campaign, source, parent, request) is None
    assert len(published) == 1
    assert published[0]['execution_authority'] is False


def test_review_route_reuses_exact_publication_and_materializes_separate_tasks(monkeypatch):
    from app.services import alpha_campaign, evaluator_routing
    db, campaign, _, _, _, _, _ = fixture()
    task = ready_task()
    identity = dict(agent_id=str(uuid4()), machine='vm1-developer', provider='codex',
                    model_family='test', runtime='test', context_group='producer',
                    package_digest='a'*64)
    packet = task.result['summary']['method_episode']['review_packet']
    route = SimpleNamespace(id=uuid4(), status='assigned')
    monkeypatch.setattr(service, 'require_current_method_authority', lambda *_: None)
    create = MagicMock(return_value=route)
    materialize = MagicMock()
    published = []
    monkeypatch.setattr(evaluator_routing, 'create_route', create)
    monkeypatch.setattr(evaluator_routing, 'validated_alpha_strategy_reviews', lambda *_, **__: None)
    monkeypatch.setattr(alpha_campaign, '_materialize_strategy_review_tasks', materialize)
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: published.append(args[-1]))
    db.scalar.side_effect = [None]
    assert service.route_method_review(db, campaign, task, packet, identity) == (route, None)
    assert create.call_args.args[1].required_review_kinds == ['strategy_spec', 'causality_leakage']
    db.scalar.side_effect = [SimpleNamespace(payload=published[0])]
    db.get.return_value = route
    assert service.route_method_review(db, campaign, task, packet, identity) == (route, None)
    create.assert_called_once()
    assert materialize.call_count == 2  # Existing AR task identities handle repeated reconciliation.
    published[0]['qualification'] = {}
    db.scalar.side_effect = [SimpleNamespace(payload=published[0])]
    with pytest.raises(ValueError, match='publication changed'):
        service.route_method_review(db, campaign, task, packet, identity)


@pytest.mark.parametrize('exhausted', [False, True])
def test_campaign_rejection_corrects_or_defers_without_engineering(monkeypatch, exhausted):
    from app.services import alpha_campaign, evaluator_routing, alpha_method_recovery
    from app.services.alpha_requirements_handoff import RequirementsPending
    db, campaign, source, parent, request, _, _ = fixture()
    task = ready_task()
    task.plan_digest = '1'*64
    successor = SimpleNamespace(id=uuid4(), status='queued')
    route = SimpleNamespace(id=uuid4(), status='completed')
    monkeypatch.setattr(service, 'materialize_method_task', lambda *_: task)
    monkeypatch.setattr(alpha_method_recovery, 'recorded_successor', lambda *_: None)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: {'agent_id': 'producer'})
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: None)
    monkeypatch.setattr(service, 'route_method_review', lambda *_: (route, [SimpleNamespace(verdict='reject')]))
    def correct(*args, **kwargs):
        if exhausted:
            raise alpha_method_recovery.RecoveryDeferred('repair_or_model_budget_exhausted')
        return successor
    monkeypatch.setattr(alpha_method_recovery, 'materialize_correction', correct)
    db.scalar.side_effect = [None]
    before = deepcopy(campaign.specification)
    if exhausted:
        with pytest.raises(RequirementsPending):
            service.advance_method_task(db, campaign, source, parent, request)
        assert campaign.next_action == 'method_design_deferred'
        assert campaign.terminal_reason['detail']['reason'] == 'repair_or_model_budget_exhausted'
    else:
        assert service.advance_method_task(db, campaign, source, parent, request) is successor
        assert campaign.next_action == 'await_bounded_method_correction'
    assert campaign.specification == before


def test_missing_native_dependency_defers_before_paid_review(monkeypatch):
    from app.services import alpha_campaign, evaluator_routing, alpha_method_recovery, alpha_method_engineering
    from app.services.alpha_requirements_handoff import RequirementsPending
    from app.schemas.alpha_campaign import MethodEngineeringRequest
    from .test_alpha_method_engineering import fixture as engineering_fixture
    db, campaign, source, parent, request, _, _ = fixture()
    task = ready_task()
    task.plan_digest = '1'*64
    template, _, _, _, _, plan_digest = engineering_fixture()
    planning_id = uuid4()
    campaign.specification['method_engineering_requests'] = {task.input_contract['candidate_id']:
        MethodEngineeringRequest(contract=template, feasibility_task_id=planning_id,
                                 plan_evidence_digest=plan_digest).model_dump(mode='json')}
    monkeypatch.setattr(service, 'materialize_method_task', lambda *_: task)
    monkeypatch.setattr(alpha_method_recovery, 'recorded_successor', lambda *_: None)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: {'agent_id': 'producer'})
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: None)
    def unavailable(*args):
        raise alpha_method_engineering.MethodPlanUnavailable('Current successful native planning task required')
    monkeypatch.setattr(alpha_method_engineering, 'verified_plan_evidence', unavailable)
    review = MagicMock(side_effect=AssertionError('must not pay for review without native plans'))
    monkeypatch.setattr(service, 'route_method_review', review)
    db.scalar.side_effect = [None]
    with pytest.raises(RequirementsPending):
        service.advance_method_task(db, campaign, source, parent, request)
    review.assert_not_called()
    assert campaign.next_action == 'method_dependency_deferred'
    assert campaign.terminal_reason['detail']['feasibility_task_id'] == str(planning_id)
    assert campaign.terminal_reason['detail']['owner'] == 'native_feasibility_planner'
