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


def test_method_input_aggregate_bounds_match_worker_without_expanding_documents(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    from swarm_worker.engineering_episode import EpisodeIntegrityError
    request = fixture()[4]
    documents = [{'ordinal':i, 'text':'x'*9000} for i in range(32)]
    request['evidence_catalog'] = {service.digest(v):v for v in documents}
    assert MethodTaskContract.model_validate(request).model_dump(mode='json') == WorkerContract.model_validate(request).model_dump(mode='json')
    for count, width in [(65, 1), (1, 270000), (64, 9000)]:
        documents = [{'ordinal':i, 'text':'x'*width} for i in range(count)]
        request['evidence_catalog'] = {service.digest(v):v for v in documents}
        for model in (MethodTaskContract, WorkerContract):
            with pytest.raises((ValueError, EpisodeIntegrityError)):
                model.model_validate(request)


def test_assurance_requires_explicit_v2_authority_and_frozen_obligations():
    request = fixture()[4]
    request['policy']['allowed_method_fields'] = ['assurance']
    with pytest.raises(ValueError, match='V2 successor'):
        MethodTaskContract.model_validate(request)
    method = request['proposal']['method']
    method.update(schema_version='design-adequacy-contract-v2', experiment={}, calibration_design={},
        calibration={'max_work_units': 100},
        assurance={'required_outputs': ['target'], 'workload': {'caps': {'statistic_evaluation': 100}}})
    assert MethodTaskContract.model_validate(request).proposal['method'] == method
    method['assurance']['required_outputs'] = []
    with pytest.raises(ValueError, match='frozen output obligations'):
        MethodTaskContract.model_validate(request)


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


@pytest.mark.parametrize('lane', ['method_engineering_requests', 'method_execution_preparation_requests'])
def test_execution_lanes_require_data_declaration_before_method_author_creation(monkeypatch, lane):
    from app.services import alpha_campaign
    from app.services.alpha_data_prerequisites import DataPrerequisiteUnavailable
    db, campaign, source, parent, request, _, _ = fixture()
    campaign.specification[lane] = {request['candidate_id']: {'frozen': 'request'}}
    before = deepcopy(campaign.specification)
    monkeypatch.setattr(alpha_campaign, '_source_bindings', lambda *_: [])
    saved = MagicMock()
    monkeypatch.setattr(service, 'persist_new_task', saved)
    with pytest.raises(DataPrerequisiteUnavailable) as caught:
        service.materialize_method_task(db, campaign, source, parent, request)
    assert caught.value.reason_code == 'assess_method_data_prerequisites'
    saved.assert_not_called()
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


def ready_task(*, structured=False, consistency=None, projected=False, max_tool_calls=4, observed=False, raw=None):
    raw = deepcopy(raw) if raw is not None else fixture()[4]
    raw['policy']['max_tool_calls'] = max_tool_calls
    if observed:
        raw['policy']['investigation_tools'] = ['inspect_contract']
    if structured:
        raw['proposal']['method'].update(experiment={'synthetic': True}, calibration_design={})
    c = MethodTaskContract.model_validate(raw)
    task = SimpleNamespace(id=uuid4(), status='succeeded', input_contract=raw,
                           started_at=datetime.now(timezone.utc))
    proposal = deepcopy(c.proposal)
    evidence_catalog = deepcopy(c.evidence_catalog)
    observation = {'schema_version': 'synthetic-inspection-v1', 'execution_authority': False}
    observation_ref = service.digest(observation)
    if observed:
        proposal['method']['estimator_id'] = 'fixture justification ' + observation_ref
        evidence_catalog[observation_ref] = observation
    payload = proposal['method']
    if c.diagnostic == 'requirements_feasibility_v1':
        from app.contracts.requirements_repair import planning_payload
        payload = planning_payload(proposal, evidence_catalog, c.base_ref, service.digest)
    request = dict(schema_version='native-diagnostic-request-v1', tool=c.diagnostic,
        source_commit=c.base_ref, subject_digest=service.digest(proposal), payload=payload)
    receipt = dict(schema_version='native-diagnostic-receipt-v1', tool=c.diagnostic,
        request_digest=service.digest(request), source_commit=c.base_ref,
        subject_digest=service.digest(proposal), evidence_catalog_digest=service.digest(evidence_catalog),
        execution_authority=False, scientific_certification=False, market_data_used=False,
        implementation_digests={'fixture': '0'*64}, evidence_kind='design_diagnostic',
        result={'status': 'requires_independent_review_and_native_calibration',
                'contract_digest': service.digest(proposal['method'])})
    if consistency is not None:
        receipt['result']['consistency'] = consistency
    if c.diagnostic == 'requirements_feasibility_v1':
        report = dict(schema_version='native-requirements-feasibility-v1',
            source_commit=c.base_ref, input_digest=service.digest(payload), status='ready', reasons=[],
            validation_plans={mode: dict(status='ready', reasons=[]) for mode in ['smoke', 'scientific']},
            scientific_certification=False, execution_authority=False,
            coverage_successor_proposal=None, successor_validation_plans=None)
        report['report_digest'] = service.digest(report)
        receipt['result'] = report
    if projected:
        from app.contracts.diagnostic_evidence import referenced_catalog
        receipt['evidence_catalog_digest'] = service.digest(referenced_catalog(payload, evidence_catalog, service.digest))
    receipt['receipt_digest'] = service.digest(receipt)
    state = dict(binding=dict(task_id=str(task.id), source_commit=c.base_ref,
        mandate_digest=c.mandate_digest, findings_digest=c.findings_digest,
        contract_digest=service.digest(raw), kind='method-episode-v1',
        initial_digest=service.digest(c.proposal), policy=c.policy.model_dump()),
        proposal=proposal, scientific_approval=False, execution_authority=False,
        model_calls=0, repairs=0, tool_calls=1, reserved_work=c.policy.tool_work_limit,
        deadline=task.started_at.timestamp() + c.policy.max_duration_seconds,
        status='ready_for_independent_review', evidence={service.digest(receipt): receipt})
    if observed:
        from app.contracts.recovery_investigation import catalog
        state['binding']['investigation_catalog'] = catalog(c.policy.investigation_tools)
        state['observations'] = [{'request': {'tool': 'inspect_contract'}, 'evidence_refs': [observation_ref]}]
        state['evidence'][observation_ref] = observation
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


@pytest.mark.parametrize('projected', [False, True])
def test_ready_method_verifies_observed_catalog_without_granting_approval(projected):
    task = ready_task(observed=True, projected=projected)
    assert service.verified_method_result(task)['scientific_approval'] is False
    result = task.result['summary']['method_episode']
    result['state']['observations'] = []
    result['review_packet']['method_episode_digest'] = service.digest(result['state'])
    result['result_digest'] = service.digest({k:v for k,v in result.items() if k != 'result_digest'})
    with pytest.raises(ValueError, match='exact current native diagnosis'):
        service.verified_method_result(task)


def test_observation_catalog_parity_excludes_author_outputs(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'worker/src'))
    from swarm_worker.recovery_investigation import diagnostic_catalog as worker_catalog
    from app.contracts.recovery_investigation import diagnostic_catalog
    from copy import deepcopy
    initial = {'initial': True}
    observed = {'schema_version': 'fixture-observation', 'scientific_approval': False}
    authored = {'rationale': 'unsupported author claim'}
    initial_catalog = {service.digest(initial): initial}
    ref = service.digest(observed)
    state = {'evidence': {ref: observed, service.digest(authored): authored},
             'observations': [{'request': {'tool': 'inspect_contract'}, 'evidence_refs': [ref]}]}
    for helper in (diagnostic_catalog, worker_catalog):
        assert helper(initial_catalog, state, ['inspect_contract'], service.digest) == initial_catalog | {ref: observed}
        assert helper(initial_catalog, {}, [], service.digest) == initial_catalog
        with pytest.raises(ValueError, match='Unapproved'):
            helper(initial_catalog, state, [], service.digest)
        reread = deepcopy(state)
        reread['observations'][0]['request']['tool'] = 'read_evidence'
        with pytest.raises(ValueError, match='author claim'):
            helper(initial_catalog, reread, ['read_evidence'], service.digest)
        broken = deepcopy(state)
        broken['evidence'][ref]['scientific_approval'] = True
        with pytest.raises(ValueError, match='custody'):
            helper(initial_catalog, broken, ['inspect_contract'], service.digest)
        missing = deepcopy(state)
        del missing['evidence'][ref]
        with pytest.raises(ValueError, match='custody'):
            helper(initial_catalog, missing, ['inspect_contract'], service.digest)


def test_investigation_enabled_worker_result_publishes_with_exact_catalog(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    from swarm_worker.method_episode import MethodEpisode
    from swarm_worker.recovery_investigation import catalog as worker_catalog
    from app.contracts.recovery_investigation import catalog
    task = ready_task()
    task.input_contract['policy']['investigation_tools'] = ['inspect_contract', 'read_evidence']
    contract = WorkerContract.model_validate(task.input_contract)
    assert contract.model_dump(mode='json') == MethodTaskContract.model_validate(task.input_contract).model_dump(mode='json')
    assert worker_catalog(contract.policy.investigation_tools) == catalog(contract.policy.investigation_tools)
    retained = {'failure': 'shared parser defect', 'synthetic': True}
    ref = service.digest(retained)
    async def diagnose(*_):
        return dict(disposition='repair', evidence={ref: retained}, findings=[dict(
            requirement_ref='parser', evidence_digest=ref, message='Fixture failure', verification='fixture')], work_units=1)
    async def propose(context, *_):
        return dict(action='escalate', disposition='infrastructure_repair', owner='platform',
            recovery_condition='Independent shared-code review and deployment', evidence_refs=[ref],
            rationale='Candidate corrections cannot fix the parser')
    episode = MethodEpisode(tmp_path/'episode', binding=dict(task_id=str(task.id),
        source_commit=contract.base_ref, mandate_digest=contract.mandate_digest,
        findings_digest=contract.findings_digest, contract_digest=service.digest(task.input_contract)),
        proposal=contract.proposal, policy=contract.policy, diagnose=diagnose, propose=propose,
        authorized=lambda _: True, investigate=diagnose,
        investigation_catalog=worker_catalog(contract.policy.investigation_tools))
    state = asyncio.run(episode.run())
    result = dict(schema_version='method-task-result-v1', contract_digest=service.digest(task.input_contract),
        state=state, scientific_approval=False, execution_authority=False)
    result['result_digest'] = service.digest(result)
    task.result = {'summary': {'method_episode': result}}
    assert service.verified_method_result(task)['state']['escalation']['owner'] == 'platform'
    state['binding']['investigation_catalog']['read_evidence']['description'] = 'Changed semantics'
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    with pytest.raises(ValueError, match='binding mismatch'):
        service.verified_method_result(task)


@pytest.mark.parametrize('defect', [None, 'evidence', 'scope'])
def test_investigation_ready_packet_still_requires_exact_review_evidence(defect):
    from app.contracts.recovery_investigation import catalog
    task = ready_task()
    task.input_contract['policy']['investigation_tools'] = ['inspect_contract']
    result = task.result['summary']['method_episode']
    result['contract_digest'] = service.digest(task.input_contract)
    state = result['state']
    state['binding'].update(contract_digest=result['contract_digest'],
        policy=MethodTaskContract.model_validate(task.input_contract).policy.model_dump(),
        investigation_catalog=catalog(['inspect_contract']))
    result['review_packet']['method_episode_digest'] = service.digest(state)
    if defect == 'evidence':
        result['review_packet']['evidence'] = {}
    elif defect == 'scope':
        state['proposal']['scientific_identity']['question'] = 'Unapproved new question'
        result['review_packet']['method_episode_digest'] = service.digest(state)
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    if defect:
        with pytest.raises(ValueError):
            service.verified_method_result(task)
    else:
        assert service.verified_method_result(task)['state']['status'] == 'ready_for_independent_review'


def test_projected_native_receipt_is_reconstructed_and_verified(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'worker/src'))
    from swarm_worker.native_diagnostic_client import referenced_catalog as worker_projection
    from app.contracts.diagnostic_evidence import referenced_catalog
    leaf = {'equation': 'x[t-1]'}
    parent = {'reference': service.digest(leaf)}
    catalog = {service.digest(v):v for v in [leaf, parent, {'historical':True}]}
    payload = {'reference': service.digest(parent)}
    assert referenced_catalog(payload, catalog, service.digest) == worker_projection(payload, catalog)
    assert len(referenced_catalog(payload, catalog, service.digest)) == 2
    task = ready_task(projected=True)
    assert service.verified_method_result(task)['scientific_approval'] is False


@pytest.mark.parametrize('mode', ['historical', 'missing_current', 'ambiguous_current'])
def test_current_diagnosis_selected_by_complete_bindings(mode):
    task = ready_task()
    result = task.result['summary']['method_episode']
    state = result['state']
    receipt = deepcopy(next(iter(state['evidence'].values())))
    if mode != 'ambiguous_current':
        receipt['evidence_catalog_digest'] = 'f' * 64
    else:
        receipt['implementation_digests'] = {'different': '1' * 64}
    receipt['receipt_digest'] = service.digest({k: v for k, v in receipt.items() if k != 'receipt_digest'})
    if mode == 'missing_current':
        state['evidence'].clear()
    state['evidence'][service.digest(receipt)] = receipt
    result['review_packet']['evidence'] = deepcopy(state['evidence'])
    result['review_packet']['method_episode_digest'] = service.digest(state)
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    if mode == 'historical':
        assert service.verified_method_result(task)['scientific_approval'] is False
    else:
        with pytest.raises(ValueError, match='exact current native diagnosis'):
            service.verified_method_result(task)


def test_structured_method_cannot_use_legacy_or_failed_consistency_receipt():
    for consistency in (None, {'status': 'unverified_legacy_prose'},
                        {'status': 'structurally_consistent', 'finding_count': 1, 'findings': []}):
        with pytest.raises(ValueError, match='consistency readiness'):
            service.verified_method_result(ready_task(structured=True, consistency=consistency))
    result = service.verified_method_result(ready_task(structured=True, consistency={
        'status': 'structurally_consistent', 'finding_count': 0, 'findings': []}))
    assert result['scientific_approval'] is False


@pytest.mark.parametrize('omit_document', [False, True])
def test_compact_review_preserves_every_underlying_document(omit_document):
    task = ready_task()
    result = task.result['summary']['method_episode']
    state = result['state']
    envelope = dict(disposition='ready', findings=[], work_units=1,
                    evidence=deepcopy(state['evidence']))
    state['evidence'][service.digest(envelope)] = envelope
    result['review_packet']['method_episode_digest'] = service.digest(state)
    if omit_document:
        result['review_packet']['evidence'].pop(next(iter(envelope['evidence'])))
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    if omit_document:
        with pytest.raises(ValueError, match='packet differs'):
            service.verified_method_result(task)
    else:
        assert service.verified_method_result(task)['scientific_approval'] is False


@pytest.mark.parametrize('tamper', [None, 'reference', 'envelope', 'audit', 'cycle', 'packet_ref', 'packet_digest', 'proposal_ref', 'duplicate_proposal'])
@pytest.mark.parametrize('large_history', [False, True, 'over_wire'])
@pytest.mark.parametrize('proposal_reference', [False, True])
@pytest.mark.parametrize('max_tool_calls', [1, 4])
def test_v2_transport_reconstructs_exact_audit_state(tamper, large_history, proposal_reference, max_tool_calls):
    task = ready_task(max_tool_calls=max_tool_calls)
    result = task.result['summary']['method_episode']
    state = result['state']
    if large_history:
        retained = {'synthetic_history': 'x' * (300000 if large_history == 'over_wire' else 140000)}
        state['evidence'][service.digest(retained)] = retained
        result['review_packet']['evidence'][service.digest(retained)] = retained
    envelope = dict(disposition='ready', findings=[], work_units=1,
                    evidence=deepcopy(state['evidence']))
    key = service.digest(envelope)
    full = deepcopy(state)
    full['evidence'][key] = envelope
    result.update(schema_version='method-task-result-v2',
                  audit_state_digest=service.digest(full),
                  state_evidence_envelopes={key: envelope | {'evidence': sorted(envelope['evidence'])}})
    result['review_packet']['method_episode_digest'] = service.digest(full)
    result['review_packet_digest'] = service.digest(result['review_packet'])
    result['review_evidence_refs'] = sorted(result['review_packet'].pop('evidence'))
    if proposal_reference or tamper in {'proposal_ref', 'duplicate_proposal'}:
        result['review_proposal_digest'] = service.digest(result['review_packet'].pop('proposal'))
    if tamper == 'reference':
        result['state_evidence_envelopes'][key]['evidence'] = ['f'*64]
    elif tamper == 'envelope':
        result['state_evidence_envelopes'][key]['work_units'] += 1
    elif tamper == 'audit':
        result['audit_state_digest'] = 'f'*64
    elif tamper == 'cycle':
        result['state_evidence_envelopes'][key]['evidence'] = [key]
    elif tamper == 'packet_ref':
        result['review_evidence_refs'] = ['f'*64]
    elif tamper == 'packet_digest':
        result['review_packet_digest'] = 'f'*64
    elif tamper == 'proposal_ref':
        result['review_proposal_digest'] = 'f'*64
    elif tamper == 'duplicate_proposal':
        result['review_packet']['proposal'] = deepcopy(state['proposal'])
    result['result_digest'] = service.digest({k: v for k, v in result.items() if k != 'result_digest'})
    if large_history == 'over_wire':
        from app.contracts.method_result_transport import encode
        task.result['summary']['method_episode'] = encode(result)
    before = deepcopy(task.result)
    if tamper:
        with pytest.raises(ValueError):
            service.verified_method_result(task)
    else:
        verified = service.verified_method_result(task)
        assert verified['state'] == full
        assert verified['result_digest'] == result['result_digest']
    assert task.result == before


def test_large_method_handoff_keeps_proposal_once_and_hash_bound():
    import json
    proposal = {'synthetic': 'p' * 45000}
    packet = {'proposal': proposal, 'evidence': {'synthetic': 'e' * 180000}}
    before = deepcopy(packet)
    qualification = service.method_review_qualification(packet)
    assert qualification['card']['proposal_digest'] == service.digest(proposal)
    assert qualification['card']['proposal_location'] == 'qualification.artifact_bundle.method_review_packet.proposal'
    assert qualification['artifact_bundle']['method_review_packet'] == before
    assert packet == before
    assert len(json.dumps(qualification).encode()) < 250000
    small = {'proposal': {'small': True}}
    assert service.method_review_qualification(small)['card'] == small['proposal']


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


@pytest.mark.parametrize('authorized', [False, True])
def test_accepted_method_prepares_execution_only_with_explicit_request(monkeypatch, authorized):
    from app.services import alpha_campaign, evaluator_routing, alpha_method_recovery, alpha_execution_preparation
    from app.services import alpha_data_prerequisites
    db, campaign, source, parent, request, _, _ = fixture()
    task = ready_task()
    task.plan_digest = '1'*64
    monkeypatch.setattr(alpha_campaign, '_source_bindings', lambda *_: [])
    data_gate = MagicMock(return_value={})
    monkeypatch.setattr(alpha_data_prerequisites, 'require_data_prerequisites', data_gate)
    preparation = SimpleNamespace(status='pending_approval')
    if authorized:
        campaign.specification['method_execution_preparation_requests'] = {task.input_contract['candidate_id']:{'frozen':'request'}}
    monkeypatch.setattr(alpha_method_recovery,'recorded_successor',lambda *_:None)
    monkeypatch.setattr(service,'materialize_method_task',lambda *_:task)
    monkeypatch.setattr(evaluator_routing,'task_producer_identity',lambda *_:{'agent_id':'producer'})
    monkeypatch.setattr(service,'route_method_review',lambda *_:(SimpleNamespace(status='completed'),
        [SimpleNamespace(verdict='approve'),SimpleNamespace(verdict='approve')]))
    monkeypatch.setattr(alpha_campaign,'_append_event',lambda *_:None)
    dispatch=MagicMock(return_value=preparation)
    monkeypatch.setattr(alpha_execution_preparation,'materialize_execution_preparation',dispatch)
    db.scalar.side_effect=None
    db.scalar.return_value=None
    result=service.advance_method_task(db,campaign,source,parent,request)
    if authorized:
        assert result is preparation
        assert campaign.phase=='execution_preparation'
        assert campaign.next_action=='approve_execution_preparation'
        dispatch.assert_called_once()
        data_gate.assert_called_once()
    else:
        assert result is None
        assert campaign.next_action=='materialize_accepted_method_handoff'
        dispatch.assert_not_called()
        data_gate.assert_not_called()


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


@pytest.mark.parametrize('reason', ['produce_admitted_method_data', 'assess_method_data_prerequisites'])
@pytest.mark.parametrize('lane', ['engineering', 'preparation'])
def test_data_prerequisite_gate_stops_before_review_and_engineering(monkeypatch, reason, lane):
    from copy import deepcopy
    from app.services import alpha_campaign, evaluator_routing, alpha_method_recovery, alpha_method_engineering
    from app.services import alpha_data_prerequisites, alpha_execution_preparation
    from app.services.alpha_data_prerequisites import DataPrerequisiteUnavailable
    from app.services.alpha_requirements_handoff import RequirementsPending
    from app.schemas.alpha_campaign import MethodEngineeringRequest
    from .test_alpha_method_engineering import fixture as engineering_fixture
    db, campaign, source, parent, request, _, _ = fixture()
    task = ready_task()
    task.plan_digest = '1'*64
    template, _, _, _, _, plan_digest = engineering_fixture()
    campaign.specification['method_engineering_requests'] = {task.input_contract['candidate_id']:
        MethodEngineeringRequest(contract=template, feasibility_task_id=uuid4(),
                                 plan_evidence_digest=plan_digest).model_dump(mode='json')}
    if lane == 'preparation':
        campaign.specification.pop('method_engineering_requests')
        campaign.specification['method_execution_preparation_requests'] = {
            task.input_contract['candidate_id']: {'frozen': 'request'}}
    monkeypatch.setattr(alpha_campaign, '_source_bindings', lambda *_: [])
    before = deepcopy(campaign.specification)
    monkeypatch.setattr(service, 'materialize_method_task', lambda *_: task)
    monkeypatch.setattr(alpha_method_recovery, 'recorded_successor', lambda *_: None)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: {'agent_id': 'producer'})
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: None)
    detail = {'missing': 'registered membership', 'execution_authority': False}
    monkeypatch.setattr(alpha_method_engineering, 'verified_plan_evidence',
                        MagicMock(side_effect=DataPrerequisiteUnavailable(reason, detail)))
    monkeypatch.setattr(alpha_data_prerequisites, 'require_data_prerequisites',
                        MagicMock(side_effect=DataPrerequisiteUnavailable(reason, detail)))
    review = MagicMock(side_effect=AssertionError('paid review must not start'))
    engineer = MagicMock(side_effect=AssertionError('engineering must not start'))
    monkeypatch.setattr(service, 'route_method_review', review)
    monkeypatch.setattr(alpha_method_engineering, 'materialize_method_engineering', engineer)
    monkeypatch.setattr(alpha_execution_preparation, 'materialize_execution_preparation', engineer)
    db.scalar.side_effect = [None]
    with pytest.raises(RequirementsPending):
        service.advance_method_task(db, campaign, source, parent, request)
    review.assert_not_called()
    engineer.assert_not_called()
    assert campaign.next_action == reason
    assert campaign.terminal_reason['detail']['missing'] == 'registered membership'
    assert campaign.specification == before
