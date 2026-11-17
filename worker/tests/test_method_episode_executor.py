import asyncio
import json
import sys

import pytest

from swarm_worker.engineering_episode import canonical_digest
from swarm_worker.executors.method_episode import correction_proposer
from swarm_worker.method_episode import MethodCapacityUnavailable
from test_engineering_episode_executor import fixture, step


async def heartbeat(_): pass


@pytest.mark.asyncio
async def test_model_adapter_retains_context_and_parses_proposal(tmp_path, monkeypatch):
    executor, _, _, workspace = fixture(tmp_path, '1', 1)
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE', 'subscription')
    calls = []
    async def model(**kwargs):
        calls.append(kwargs)
        assert '--sandbox' in kwargs['args'] and 'read-only' in kwargs['args']
        (kwargs['workspace'].artifacts/'correction.json').write_text(json.dumps({
            'changes_json':'{"lag":1}', 'addressed_findings':['a'*64], 'rationale':'Completed bars'}))
        return step('method-proposal', kwargs['workspace'])
    executor._run_codex = model
    callback = correction_proposer(executor, workspace, heartbeat, read_evidence=lambda _: {'observed':0})
    context = {'findings':[{'evidence_digest':'b'*64}], 'finding_digests':['a'*64]}
    result = await callback(context, 'c'*64, 30)
    assert result['changes'] == {'lag':1}
    assert 'current_evidence' in calls[0]['prompt']
    assert 'environment_overrides' in calls[0]


@pytest.mark.asyncio
async def test_quota_log_paths_are_resolved_inside_operation(tmp_path, monkeypatch):
    executor, _, _, workspace = fixture(tmp_path, '1', 1)
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    async def model(**kwargs):
        result = step('method-proposal', kwargs['workspace'])
        (kwargs['workspace'].logs/'method-proposal.stderr.log').write_text('You have hit your usage limit')
        return result.model_copy(update={'success':False, 'return_code':1})
    executor._run_codex = model
    callback = correction_proposer(executor, workspace, heartbeat, read_evidence=lambda _: {})
    with pytest.raises(MethodCapacityUnavailable):
        await callback({'findings':[]}, 'c'*64, 30)


@pytest.mark.asyncio
async def test_cancelled_model_runner_terminates_subprocess(tmp_path):
    executor, _, _, workspace = fixture(tmp_path, '1', 1)
    processes = []
    start = executor._runner.start
    async def capture(*args, **kwargs):
        running = await start(*args, **kwargs)
        processes.append(running.process)
        return running
    executor._runner.start = capture
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(executor._run_codex(name='cancel-probe',
            args=[sys.executable,'-c','import time; time.sleep(60)'], prompt='offline fixture',
            workspace=workspace, heartbeat=heartbeat, heartbeat_failures=[], timeout_seconds=60), .2)
    assert processes and processes[0].returncode is not None
