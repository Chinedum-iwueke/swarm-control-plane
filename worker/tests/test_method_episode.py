import asyncio
from copy import deepcopy

import pytest

from swarm_worker.engineering_episode import canonical_digest, EpisodeIntegrityError
from swarm_worker.method_episode import MethodEpisode, MethodEpisodePolicy, MethodCapacityUnavailable


BINDING = dict(task_id='task-1', source_commit='a'*40, mandate_digest='b'*64, findings_digest='c'*64)


def test_diagnostic_evidence_allows_catalog_plus_one_receipt_only():
    from swarm_worker.method_episode import Diagnosis
    from swarm_worker.method_task import MethodTaskContract
    from test_alpha_method_design import contract
    evidence = {canonical_digest({'fixture': i}): {'fixture': i} for i in range(65)}
    assert len(Diagnosis(disposition='ready', findings=[], evidence=evidence, work_units=1).evidence) == 65
    source = contract('a' * 40)
    source['evidence_catalog'] = evidence
    with pytest.raises(ValueError):
        MethodTaskContract.model_validate(source)
    evidence[canonical_digest({'fixture': 65})] = {'fixture': 65}
    with pytest.raises(ValueError):
        Diagnosis(disposition='ready', findings=[], evidence=evidence, work_units=1)


@pytest.mark.asyncio
async def test_large_diagnostic_envelope_keeps_individual_document_bounds(tmp_path):
    docs = [{'ordinal':i, 'evidence':'x'*9000} for i in range(32)]
    catalog = {canonical_digest(v):v for v in docs}
    async def large(*_):
        return dict(disposition='ready', findings=[], evidence=catalog, work_units=1)
    state = await episode(tmp_path, diagnose=large).run()
    assert state['status'] == 'ready_for_independent_review'
    assert all(state['evidence'][k] == v for k,v in catalog.items())


def diagnosis(proposal, disposition=None):
    evidence = {'source_commit': BINDING['source_commit'], 'proposal_digest': canonical_digest(proposal),
                'observed': proposal['method'].get('lag', 0)}
    digest = canonical_digest(evidence)
    valid = proposal['method'].get('lag') == 1
    return dict(disposition=disposition or ('ready' if valid else 'repair'),
        findings=[] if valid else [dict(requirement_ref='completed_bar', evidence_digest=digest,
            message='Feature must be lagged.', verification='Native timing check')],
        evidence={digest: evidence}, work_units=10)


async def diagnose(proposal, *_):
    return diagnosis(proposal)


async def propose(context, *_):
    return dict(changes={'lag': 1}, addressed_findings=[canonical_digest(f) for f in context['findings']],
                rationale='Use completed observations.')


def episode(tmp_path, **kwargs):
    return MethodEpisode(tmp_path/'episode', binding=kwargs.pop('binding', BINDING),
        proposal=kwargs.pop('proposal', dict(scientific_identity={'target': 'return'},
            support_minima={'observations':100}, method={'lag':0})),
        policy=kwargs.pop('policy', MethodEpisodePolicy(allowed_method_fields=['lag'])),
        diagnose=kwargs.pop('diagnose', diagnose), propose=kwargs.pop('propose', propose),
        authorized=kwargs.pop('authorized', lambda _: True), **kwargs)


@pytest.mark.asyncio
async def test_complete_repair_is_retained_and_not_scientific_approval(tmp_path):
    engine = episode(tmp_path)
    state = await engine.run()
    assert state['status'] == 'ready_for_independent_review'
    assert state['model_calls'] == state['repairs'] == 1
    assert state['tool_calls'] == 2
    assert state['execution_authority'] is state['scientific_approval'] is False
    assert state['proposal']['scientific_identity'] == engine.initial['scientific_identity']
    assert await engine.run() == state
    for digest, doc in state['evidence'].items():
        assert engine.read_evidence(digest) == doc
    with pytest.raises(EpisodeIntegrityError): engine.read_evidence('../secret')


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['outputs', 'caps', 'calibration', 'empty_calibration', 'float_cap'])
async def test_assurance_correction_cannot_weaken_frozen_authority(tmp_path, change):
    assurance = {'required_outputs': ['target'], 'workload': {'caps': {'statistic_evaluation': 100}}}
    initial = dict(scientific_identity={'target': 'return'}, support_minima={'observations': 100},
        method={'schema_version': 'design-adequacy-contract-v2', 'lag': 0, 'assurance': assurance,
                'calibration': {'max_work_units': 100}})
    async def weaken(context, *_):
        altered = deepcopy(assurance)
        updates = {'assurance': altered, 'lag': 1}
        if change == 'outputs': altered['required_outputs'] = []
        elif change == 'caps': altered['workload']['caps']['statistic_evaluation'] = 200
        elif change == 'calibration': updates['calibration'] = {'max_work_units': 200}
        elif change == 'float_cap': altered['workload']['caps']['statistic_evaluation'] = 100.0
        else: updates['calibration'] = {}
        return dict(changes=updates, addressed_findings=[canonical_digest(f) for f in context['findings']], rationale='Invalid weakening fixture')
    engine = episode(tmp_path, proposal=initial, propose=weaken,
        policy=MethodEpisodePolicy(allowed_method_fields=['lag', 'assurance', 'calibration']))
    state = await engine.run()
    assert state['status'] != 'ready_for_independent_review'
    assert state['proposal'] == initial



@pytest.mark.asyncio
@pytest.mark.parametrize('disposition', ['await_data', 'scientifically_infeasible',
    'requirements_conflict', 'requires_new_question', 'await_authority_or_capacity'])
async def test_explicit_deferrals_do_not_call_model(tmp_path, disposition):
    async def blocked(proposal, *_): return diagnosis(proposal, disposition)
    engine = episode(tmp_path, diagnose=blocked)
    state = await engine.run()
    assert state['reason'] == disposition
    assert state['model_calls'] == 0
    assert await engine.run(recovery_token='unrelated') == state


@pytest.mark.asyncio
async def test_capacity_wait_requires_new_token_and_preserves_budget(tmp_path):
    async def quota(*_): raise MethodCapacityUnavailable()
    engine = episode(tmp_path, propose=quota)
    state = await engine.run()
    assert state['reason'] == 'capacity'
    assert state['model_calls'] == 1
    assert await engine.run() == state
    engine.propose = propose
    resumed = await engine.run(recovery_token='provider-probe-1')
    assert resumed['status'] == 'ready_for_independent_review'
    assert resumed['model_calls'] == 2
    assert resumed['deadline'] == state['deadline']


@pytest.mark.asyncio
async def test_same_capacity_signal_cannot_repeatedly_trigger_calls(tmp_path):
    async def quota(*_): raise MethodCapacityUnavailable()
    engine = episode(tmp_path, propose=quota)
    first = await engine.run(recovery_token='probe-1')
    assert (await engine.run(recovery_token='probe-1')) == first
    second = await engine.run(recovery_token='probe-2')
    assert second['model_calls'] == first['model_calls'] + 1
    assert (await engine.run(recovery_token='probe-2')) == second


@pytest.mark.asyncio
async def test_readiness_with_remaining_findings_and_missing_evidence_rejected(tmp_path):
    async def false_ready(proposal, *_):
        return diagnosis(proposal, 'ready')
    assert (await episode(tmp_path/'ready', diagnose=false_ready).run())['status'] == 'blocked'
    async def unbound(proposal, *_):
        result = diagnosis(proposal)
        result['findings'][0]['evidence_digest'] = 'f'*64
        return result
    assert (await episode(tmp_path/'unbound', diagnose=unbound).run())['status'] == 'blocked'


@pytest.mark.asyncio
async def test_crash_reserves_calls_and_does_not_restart_diagnosis(tmp_path):
    async def crash(*_): raise RuntimeError('worker died')
    engine = episode(tmp_path, propose=crash)
    with pytest.raises(RuntimeError): await engine.run()
    saved = engine.store.load()
    assert saved['model_calls'] == 1 and saved['pending']
    state = await episode(tmp_path).run()
    assert state['model_calls'] == 2 and state['tool_calls'] == 2
    assert any(e.get('status') == 'interrupted' for e in state['events'])


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', ['scope', 'finding', 'authority', 'unchanged'])
async def test_invalid_corrections_never_cross_review_boundary(tmp_path, bad):
    async def invalid(context, *_):
        result = await propose(context)
        if bad == 'scope': result['changes'] = {'scientific_identity': {'target': 'new'}}
        if bad == 'finding': result['addressed_findings'] = ['invented']
        if bad == 'authority': result['scientific_approval'] = True
        if bad == 'unchanged': result['changes'] = {'lag': 0}
        return result
    state = await episode(tmp_path, propose=invalid).run()
    assert state['status'] == 'blocked'
    assert state['tool_calls'] == 1


@pytest.mark.asyncio
async def test_binding_policy_and_state_integrity(tmp_path):
    engine = episode(tmp_path)
    await engine.run()
    with pytest.raises(EpisodeIntegrityError):
        await episode(tmp_path, binding={**BINDING, 'source_commit':'d'*40}).run()
    with pytest.raises(EpisodeIntegrityError):
        await episode(tmp_path, policy=MethodEpisodePolicy(allowed_method_fields=['lag'], max_repairs=3)).run()
    with engine.store.locked():
        with pytest.raises(EpisodeIntegrityError): await engine.run()


@pytest.mark.asyncio
async def test_authority_checked_between_stages_and_no_model_when_expired(tmp_path):
    calls = []
    def authority(_):
        calls.append(1)
        return len(calls) == 1
    state = await episode(tmp_path, authorized=authority).run()
    assert state['reason'] == 'authority' and state['model_calls'] == 0


@pytest.mark.asyncio
async def test_deadline_enforced_and_not_reset(tmp_path):
    async def slow(*_): await asyncio.sleep(2)
    engine = episode(tmp_path, diagnose=slow,
        policy=MethodEpisodePolicy(allowed_method_fields=['lag'], max_duration_seconds=1))
    state = await engine.run()
    assert state['reason'] == 'deadline_exhausted'
    assert (await engine.run(recovery_token='new'))['deadline'] == state['deadline']


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('max_model_calls', 0), ('max_repairs',0),
    ('max_tool_calls',1), ('max_work_units',1), ('max_context_bytes',1024)])
async def test_independent_budgets_and_context_do_not_reset(tmp_path, field, value):
    policy = MethodEpisodePolicy(allowed_method_fields=['lag'], **{field:value})
    engine = episode(tmp_path, policy=policy)
    state = await engine.run()
    assert state['status'] == 'deferred'
    assert await engine.run(recovery_token='new') == state


@pytest.mark.asyncio
async def test_diagnostic_evidence_and_work_are_not_trusted_blindly(tmp_path):
    async def invalid(proposal, *_):
        result = diagnosis(proposal)
        result['work_units'] = 10000000
        return result
    assert (await episode(tmp_path, diagnose=invalid).run())['status'] == 'blocked'


@pytest.mark.asyncio
@pytest.mark.parametrize('field,target', [('warmup',48), ('block_length',12), ('lag',1)])
async def test_materially_different_deterministic_repairs(tmp_path, field, target):
    async def native(proposal, *_):
        result = diagnosis(proposal)
        ready = proposal['method'].get(field) == target
        result['disposition'] = 'ready' if ready else 'repair'
        if ready: result['findings'] = []
        else:
            result['findings'][0].update(requirement_ref=field, message=f'Expected {target}',
                verification=f'Check {field} equals {target}')
        return result
    async def model(context, *_):
        result = await propose(context)
        result['changes'] = {field:target}
        return result
    state = await episode(tmp_path, diagnose=native, propose=model,
        policy=MethodEpisodePolicy(allowed_method_fields=[field])).run()
    assert state['status'] == 'ready_for_independent_review'
    assert state['repairs'] == 1
