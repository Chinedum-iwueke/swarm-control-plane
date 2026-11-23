import json

import pytest

from swarm_worker.author_session import session_author
from swarm_worker.engineering_episode import EpisodeIntegrityError
from test_engineering_episode_executor import fixture, step


@pytest.mark.asyncio
async def test_session_change_refused_without_latest_fallback(tmp_path,monkeypatch):
    monkeypatch.delenv('SWARM_AGENT_TOKEN',raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE','subscription')
    executor,_,_,workspace=fixture(tmp_path,'1',1)
    state={'model_calls':1}
    binding={'source_commit':'a'*40,'contract_digest':'b'*64}
    async def heartbeat(_): pass
    async def author(**kwargs):
        result=step('coding-agent',workspace)
        (workspace.logs/'coding-agent.stdout.log').write_text(json.dumps({'type':'thread.started',
            'thread_id':'11111111-1111-4111-8111-111111111111'}))
        return result
    executor._run_codex=author
    await session_author(executor,state=state,binding=binding,prompt='fixture',workspace=workspace,
        heartbeat=heartbeat,heartbeat_failures=[],remaining=10)
    executor._codex_model='different-model'
    with pytest.raises(EpisodeIntegrityError,match='binding changed'):
        await session_author(executor,state=state,binding=binding,prompt='fixture',workspace=workspace,
            heartbeat=heartbeat,heartbeat_failures=[],remaining=10)


@pytest.mark.asyncio
async def test_lost_session_identity_does_not_start_another_paid_author(tmp_path,monkeypatch):
    monkeypatch.delenv('SWARM_AGENT_TOKEN',raising=False)
    executor,_,_,workspace=fixture(tmp_path,'1',1)
    with pytest.raises(EpisodeIntegrityError,match='identity unavailable'):
        await session_author(executor,state={'model_calls':2},binding={'source_commit':'a'*40,'contract_digest':'b'*64},
            prompt='fixture',workspace=workspace,heartbeat=None,heartbeat_failures=[],remaining=10)


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['workspace', 'model', 'source', 'home'])
async def test_verified_relocation_permits_only_workspace_change(tmp_path, monkeypatch, change):
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE', 'subscription')
    executor, _, _, workspace = fixture(tmp_path, '1', 1)
    binding = {'source_commit': 'a'*40, 'contract_digest': 'b'*64}
    state = {'model_calls': 1, 'code_digest': 'unchanged'}
    calls = []

    async def author(**kwargs):
        calls.append(kwargs)
        result = step('coding-agent', workspace)
        (workspace.logs/'coding-agent.stdout.log').write_text(json.dumps({
            'type': 'thread.started', 'thread_id': '11111111-1111-4111-8111-111111111111'}))
        return result

    executor._run_codex = author
    args = dict(executor=executor, state=state, binding=binding, prompt='fixture',
                workspace=workspace, heartbeat=None, heartbeat_failures=[], remaining=10)
    await session_author(**args)
    state['author_session']['binding']['workspace'] = '/prior/task/repository'
    relocation = {'from': '/prior/task/repository', 'to': str(workspace.repository),
                  'code_digest': 'unchanged'}
    if change != 'workspace':
        state['author_session']['binding'][change] = 'changed'
    with pytest.raises(EpisodeIntegrityError, match='binding changed'):
        await session_author(**args)
    assert len(calls) == 1
    if change != 'workspace':
        with pytest.raises(EpisodeIntegrityError, match='binding changed'):
            await session_author(**args, verified_relocation=relocation)
        assert len(calls) == 1
        return
    await session_author(**args, verified_relocation=relocation)
    assert calls[-1]['args'][calls[-1]['args'].index('--cd')+1] == str(workspace.repository)
    assert 'resume' in calls[-1]['args'] and '--last' not in calls[-1]['args']
    assert state['author_session_relocations'] == [relocation]
