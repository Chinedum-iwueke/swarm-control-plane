from copy import deepcopy

import pytest

from swarm_worker.engineering_episode import canonical_digest, EpisodeIntegrityError
from swarm_worker.method_episode import MethodEpisode, MethodEpisodePolicy
from swarm_worker.executors.method_episode import unwrap_investigation_action


@pytest.mark.asyncio
@pytest.mark.parametrize('field,required', [('lag', 1), ('normalization', 'training_only'), ('bootstrap_block', 48)])
async def test_reasoning_selects_evidence_then_repairs_without_error_specific_controller(tmp_path, field, required):
    calls = []
    evidence = {'definition': field, 'required': required, 'source_commit': 'a'*40}
    ref = canonical_digest(evidence)
    async def diagnose(proposal, *_):
        report = {'valid': proposal['method'][field] == required}
        key = canonical_digest(report)
        return dict(disposition='ready' if report['valid'] else 'repair',
            findings=[] if report['valid'] else [dict(requirement_ref=field, evidence_digest=key,
                message='Implementation differs from retained definition.', verification='independent native check')],
            evidence={key: report}, work_units=1)
    async def propose(context, *_):
        calls.append(deepcopy(context))
        if not context.get('observations'):
            return dict(action='inspect', tool='inspect_definition', arguments={'digest': ref}, rationale='Resolve exact definition before changing implementation.')
        observed = engine.read_evidence(context['observations'][-1]['evidence_refs'][0])
        return dict(changes={observed['definition']: observed['required']},
            addressed_findings=context['finding_digests'], rationale='Match the retained definition.')
    async def investigate(request, proposal, operation, work, remaining):
        assert request['arguments'] == {'digest': ref}
        return dict(evidence={ref: evidence}, work_units=1)
    engine = MethodEpisode(tmp_path/'episode', binding=dict(task_id='fixture', source_commit='a'*40,
        mandate_digest='b'*64, findings_digest='c'*64),
        proposal=dict(scientific_identity={'question': 'unchanged'}, support_minima={'events': 40}, method={field: None}),
        policy=MethodEpisodePolicy(allowed_method_fields=[field], investigation_tools=['inspect_definition']),
        diagnose=diagnose, propose=propose, investigate=investigate,
        investigation_catalog={'inspect_definition': {'read_only': True, 'source_commit': 'a'*40}},
        authorized=lambda _: True)
    state = await engine.run()
    assert state['status'] == 'ready_for_independent_review'
    assert state['model_calls'] == 2 and state['tool_calls'] == 3 and state['repairs'] == 1
    assert state['proposal']['method'][field] == required
    assert state['proposal']['scientific_identity'] == engine.initial['scientific_identity']
    assert state['proposal']['support_minima'] == engine.initial['support_minima']
    assert state['execution_authority'] is state['scientific_approval'] is False
    assert await engine.run() == state
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['unknown_tool', 'repeat_tool', 'infrastructure', 'invented_evidence'])
async def test_investigation_boundaries_and_escalation(tmp_path, action):
    from test_method_episode import episode, diagnosis
    ref = canonical_digest({'log': 'retained failure'})
    async def propose(context, *_):
        if action in {'infrastructure', 'invented_evidence'}:
            return dict(action='escalate', disposition='infrastructure_repair', owner='platform-maintainer',
                recovery_condition='Review and deploy shared-code correction separately.',
                evidence_refs=context['evidence_refs'][:1] if action == 'infrastructure' else ['f'*64],
                rationale='Candidate edits cannot correct the shared parser.')
        return dict(action='inspect', tool='shell' if action == 'unknown_tool' else 'read_log',
            arguments={}, rationale='Inspect retained failure.')
    effects = []
    async def investigate(*_):
        effects.append(True)
        return dict(evidence={ref: {'log': 'retained failure'}}, work_units=1)
    engine = episode(tmp_path, policy=MethodEpisodePolicy(allowed_method_fields=['lag'], investigation_tools=['read_log']),
        propose=propose, investigate=investigate, investigation_catalog={'read_log': {'read_only': True}})
    state = await engine.run()
    assert state['proposal'] == engine.initial and state['repairs'] == 0
    if action == 'infrastructure':
        assert state['status'] == 'deferred' and state['escalation']['owner'] == 'platform-maintainer'
        assert state['reason'] == 'infrastructure_repair'
        assert await engine.run(recovery_token='not-new-code-authority') == state
    else:
        assert state['status'] == 'blocked'
    assert len(effects) == (1 if action == 'repeat_tool' else 0)


@pytest.mark.asyncio
async def test_inspection_rechecks_authority_before_effect(tmp_path):
    from test_method_episode import episode
    allowed = True
    async def propose(*_):
        nonlocal allowed
        allowed = False
        return dict(action='inspect', tool='read_log', arguments={}, rationale='Inspect failure.')
    async def forbidden(*_):
        pytest.fail('Effect ran after authority revocation')
    engine = episode(tmp_path, policy=MethodEpisodePolicy(allowed_method_fields=['lag'], investigation_tools=['read_log']),
        propose=propose, investigate=forbidden, investigation_catalog={'read_log': {'read_only': True}},
        authorized=lambda _: allowed)
    state = await engine.run()
    assert state['reason'] == 'authority' and state['tool_calls'] == 1


def test_action_envelope_cannot_mix_inspection_and_correction():
    valid = dict(action='inspect', correction=None, escalation=None,
        inspection=dict(tool='read_log', arguments_json='{}', rationale='Inspect evidence.'))
    assert unwrap_investigation_action(valid)['arguments'] == {}
    valid['correction'] = {'changes': {'lag': 1}}
    with pytest.raises(EpisodeIntegrityError): unwrap_investigation_action(valid)


@pytest.mark.asyncio
async def test_pinned_source_ignores_worktree_and_rejects_escape(tmp_path):
    import subprocess
    from swarm_worker.recovery_tools import read_pinned_source
    repository = tmp_path/'repository'
    repository.mkdir()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repository, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    file = repository/'src/bt/fixture.py'
    file.parent.mkdir(parents=True)
    file.write_text('LAG = 1\n')
    git('add', '.')
    git('commit', '-qm', 'Pinned source fixture')
    commit = git('rev-parse', 'HEAD')
    file.write_text('LAG = 999\n')
    receipt = await read_pinned_source(repository, commit, 'src/bt/fixture.py', timeout=5)
    assert receipt['content'] == 'LAG = 1\n'
    assert receipt['source_commit'] == commit and receipt['execution_authority'] is False
    missing = await read_pinned_source(repository, commit, 'src/bt/missing.py', timeout=5)
    assert missing['status'] == 'unavailable' and 'content' not in missing
    for path in ['/etc/passwd', 'src/bt/../../secret.py', '--help', '.env']:
        with pytest.raises(EpisodeIntegrityError):
            await read_pinned_source(repository, commit, path, timeout=5)


@pytest.mark.parametrize('arguments', ['[]', '{"digest":"a","digest":"b"}'])
def test_inspection_arguments_reject_ambiguous_or_non_object_payload(arguments):
    with pytest.raises(EpisodeIntegrityError):
        unwrap_investigation_action(dict(action='inspect', correction=None, escalation=None,
            inspection=dict(tool='read_evidence', arguments_json=arguments, rationale='Inspect evidence')))


def test_default_policy_preserves_old_episode_binding(tmp_path):
    from test_method_episode import episode
    engine = episode(tmp_path)
    assert 'investigation_tools' not in engine.store.binding['policy']
    assert 'investigation_catalog' not in engine.store.binding


@pytest.mark.asyncio
async def test_interrupted_inspection_keeps_reservation(tmp_path):
    import asyncio
    from test_method_episode import episode
    interrupted = True
    async def propose(*_):
        return dict(action='inspect', tool='read_log', arguments={}, rationale='Inspect retained log.')
    async def investigate(*_):
        nonlocal interrupted
        if interrupted:
            interrupted = False
            raise asyncio.CancelledError()
        document = {'observed': 'retained'}
        return dict(evidence={canonical_digest(document): document}, work_units=1)
    engine = episode(tmp_path, policy=MethodEpisodePolicy(allowed_method_fields=['lag'],
        investigation_tools=['read_log'], max_tool_calls=2), propose=propose,
        investigate=investigate, investigation_catalog={'read_log': {'read_only': True}})
    with pytest.raises(asyncio.CancelledError): await engine.run()
    state = engine.store.load()
    assert state['tool_calls'] == 2 and state['pending'] is not None
    state = await engine.run()
    assert state['reason'] == 'tool_budget_exhausted' and state['tool_calls'] == 2
