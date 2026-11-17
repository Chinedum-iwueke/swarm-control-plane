import asyncio
import json
import sys

import pytest

from swarm_worker.engineering_episode import canonical_digest
from swarm_worker.executors.method_episode import correction_proposer
from swarm_worker.executors.method_episode import correction_schema
from swarm_worker.method_episode import MethodCapacityUnavailable
from test_engineering_episode_executor import fixture, step


async def heartbeat(_): pass


def test_typed_output_limits_evidence_and_method_fields():
    schema = correction_schema(['meaningful_effect', 'calibration'], ['a'*64], ['b'*64])
    changes = schema['properties']['changes']
    assert set(changes['properties']) == {'meaningful_effect', 'calibration'}
    effect = changes['properties']['meaningful_effect']['anyOf'][0]
    assert effect['properties']['evidence_digests']['items']['enum'] == ['a'*64]
    assert effect['additionalProperties'] is False
    assert schema['properties']['addressed_findings']['items']['enum'] == ['b'*64]


@pytest.mark.asyncio
@pytest.mark.parametrize('lane', ['subscription', 'api'])
@pytest.mark.parametrize('typed', [False, True])
async def test_model_adapter_retains_context_and_parses_proposal(tmp_path, monkeypatch, lane, typed):
    executor, _, _, workspace = fixture(tmp_path, '1', 1)
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE', lane)
    calls = []
    async def model(**kwargs):
        calls.append(kwargs)
        assert 'model_provider="invariance_api"' not in kwargs['args']  # Runner routes once.
        assert '--sandbox' in kwargs['args'] and 'read-only' in kwargs['args']
        result = {'addressed_findings':['a'*64], 'rationale':'Completed bars'}
        result.update({'changes': {'dependence_assumptions': 'Completed bars'}} if typed else {'changes_json':'{"lag":1}'})
        (kwargs['workspace'].artifacts/'correction.json').write_text(json.dumps(result))
        return step('method-proposal', kwargs['workspace'])
    executor._run_codex = model
    callback = correction_proposer(executor, workspace, heartbeat,
        read_evidence=lambda ref: {'observed':0} if ref == 'b'*64 else pytest.fail('storage envelope must not be re-expanded'),
        context_evidence={'d'*64: {'retained_scientific_requirement': 'complete'}})
    context = {'findings':[{'evidence_digest':'b'*64}], 'finding_digests':['a'*64],
               'evidence_refs': ['b'*64, 'e'*64]}
    if typed:
        context['allowed_method_fields'] = ['dependence_assumptions']
    result = await callback(context, 'c'*64, 30)
    assert result['changes'] == ({'dependence_assumptions': 'Completed bars'} if typed else {'lag':1})
    assert 'current_evidence' in calls[0]['prompt']
    assert 'retained_scientific_requirement' in calls[0]['prompt']
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


def test_calibration_output_schema_is_closed_and_keeps_experiment_out_of_repairs():
    from swarm_worker.executors.method_episode import correction_schema
    schema = correction_schema(['calibration_design'], ['a'*64], ['b'*64])
    changes = schema['properties']['changes']['properties']
    assert set(changes) == {'calibration_design'}
    def check(value):
        if isinstance(value, dict):
            assert 'minProperties' not in value and 'maxProperties' not in value
            if value.get('type') == 'object':
                assert value['additionalProperties'] is False
                assert set(value['required']) == set(value['properties'])
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(schema)
