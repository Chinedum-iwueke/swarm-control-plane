"""Opt-in cross-repository replay. All evidence is synthetic; no model or market calls."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from app.schemas.method_task import MethodTaskContract as ApiContract
from app.services.alpha_method_tasks import verified_method_result


@pytest.fixture
def runtime(monkeypatch):
    root = os.environ.get('BULLETPROOF_SOURCE_ROOT')
    if not root:
        pytest.skip('Set BULLETPROOF_SOURCE_ROOT for explicit cross-repository replay')
    assert (Path(root)/'src/bt/governance/method_assurance.py').is_file()
    cp = Path(__file__).parents[2]
    for path in [Path(root)/'src', cp/'worker/src', cp/'worker/tests']:
        monkeypatch.syspath_prepend(str(path))


def method():
    from test_alpha_method_design import contract
    raw = contract('a'*40)
    m = raw['proposal']['method']
    m.update(schema_version='design-adequacy-contract-v2',
        experiment=dict(purpose='diagnostic', statistic_id='synthetic_contrast', inner_replicates=199,
            variants=[dict(id='v1', event_probability=.1)],
            partitions=[dict(id='test', rows=100)], families=[dict(id='primary', variant_ids=['v1'])]),
        calibration_design=dict(purpose='diagnostic', statistic_id='synthetic_contrast', scenarios=[
            dict(id='null_iid', families=[dict(id='primary', variant_ids=['v1'])],
                cells=[dict(partition_id='test', variant_id='v1', event_probability=.1,
                            expected_events=10, sampling_rule='Synthetic sampling rule, not market evidence.')],
                joint_generation='Synthetic independent primitive law for contract testing only.',
                null_or_effect='Synthetic null contrast for wire-contract testing only.',
                estimator_application='Synthetic estimator application; no scientific claim.',
                seed_schedule='Synthetic deterministic seed for contract testing only.',
                outputs='Synthetic bounded output, not a scientific calibration result.',
                event_rate_mode='registered', event_rate_assumption='Synthetic assumption, not observed support.')]),
        assurance=dict(required_outputs=['target'], definitions=[
            dict(id='input', kind='primitive', dependencies=[], statement='Synthetic initialized primitive.', evidence_digest=None, pointer=None),
            dict(id='target', kind='derived', dependencies=['input'], statement='target = abs(input)', evidence_digest=None, pointer=None)],
            workload=dict(caps={'statistic_evaluation': 100000}, stages=[
                dict(id=p, phase=p, unit='statistic_evaluation', factors={'calls': 10}, not_applicable_reason=None)
                for p in ['generation', 'fit', 'solve', 'verification', 'bootstrap']])) )
    raw['policy']['allowed_method_fields'] = ['assurance']
    return raw


def test_worker_api_v2_normalization_and_invalid_authority_match(runtime):
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    raw = method()
    assert WorkerContract.model_validate(raw).model_dump(mode='json') == ApiContract.model_validate(raw).model_dump(mode='json')
    for corrupt in ['bool_cap', 'duplicate_root', 'budget_mismatch', 'untyped_caps']:
        changed = deepcopy(raw)
        a = changed['proposal']['method']['assurance']
        if corrupt == 'bool_cap': a['workload']['caps']['statistic_evaluation'] = True
        elif corrupt == 'duplicate_root': a['required_outputs'].append('target')
        elif corrupt == 'budget_mismatch': a['workload']['caps']['statistic_evaluation'] += 1
        else: a['workload']['caps'] = ['uncapped']
        for model in [WorkerContract, ApiContract]:
            with pytest.raises(ValueError): model.model_validate(changed)


@pytest.mark.asyncio
async def test_actual_pinned_native_subprocess(runtime):
    import subprocess
    from swarm_worker.native_diagnostic_client import NativeDiagnosticClient
    from swarm_worker.engineering_episode import canonical_digest as digest
    root = Path(os.environ['BULLETPROOF_SOURCE_ROOT'])
    source = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    raw = method()
    client = NativeDiagnosticClient(root, root/'.venv/bin/python', source)
    receipt = await client.run(tool='design_adequacy_v1', subject_digest=digest(raw['proposal']),
        payload=raw['proposal']['method'], catalog=raw['evidence_catalog'], work_limit=250000, timeout=30)
    assert receipt['source_commit'] == source
    assert receipt['result']['consistency']['status'] == 'structurally_consistent'
    assert 'method_assurance.py' in receipt['implementation_digests']
    assert receipt['scientific_certification'] is receipt['execution_authority'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['repair', 'capacity'])
async def test_native_worker_publication_and_api_replay(runtime, tmp_path, monkeypatch, mode):
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from app.services.graph import digest_document as digest
    from bt.governance.diagnostic_tools import run_diagnostic
    from swarm_worker.executors.alpha_method_design import AlphaMethodDesignExecutor
    from swarm_worker.workflows import WorkflowLoader
    from test_engineering_episode_executor import fixture
    from swarm_worker.executors.method_episode import correction_schema
    import subprocess

    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    raw = method()
    raw['base_ref'] = workspace.metadata.resolved_base_commit
    m = raw['proposal']['method']
    corrected = deepcopy(m['assurance'])
    if mode == 'repair': m['assurance']['definitions'][1]['dependencies'] = ['missing']
    else: m['assurance']['workload']['stages'][0]['factors']['calls'] = 100001
    task.input_contract, task.task_type = raw, 'alpha_method_design'
    task.approval_policy = {'campaign_digest': 'f'*64}
    model_calls, native_calls = [], []

    async def native(self, **kwargs):
        native_calls.append(kwargs)
        request = dict(schema_version='native-diagnostic-request-v1', tool=kwargs['tool'],
            source_commit=raw['base_ref'], subject_digest=kwargs['subject_digest'], payload=kwargs['payload'])
        return run_diagnostic(request, runtime_source_commit=raw['base_ref'], evidence_catalog=kwargs['catalog'])

    def proposer(*args, **kwargs):
        async def propose(context, *_):
            model_calls.append(context)
            schema = correction_schema(['assurance'], raw['evidence_catalog'], context['finding_digests'], corrected)
            value = deepcopy(corrected)
            # Exercise the provider's strict, closed factor shape, not a loose mock.
            factor_names = schema['properties']['changes']['properties']['assurance']['anyOf'][0]['properties']['workload']['properties']['stages']['items']['anyOf'][0]['properties']['factors']['required']
            for stage in value['workload']['stages']:
                stage['factors'] = dict.fromkeys(factor_names, 1) | stage['factors']
            output = dict(changes={'assurance': value}, addressed_findings=context['finding_digests'], rationale='Synthetic definition dependency repair.')
            subprocess.run([str(Path(os.environ['BULLETPROOF_SOURCE_ROOT'])/'.venv/bin/python'), '-c',
                'import json,sys,jsonschema; v=json.load(sys.stdin); jsonschema.validate(v[0],v[1])'],
                input=json.dumps([output, schema]), text=True, capture_output=True, check=True, timeout=20)
            return output
        return propose

    async def heartbeat(_): pass
    async def permit(): return {'allowed': True}
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.NativeDiagnosticClient.run', native)
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.correction_proposer', proposer)
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.model_capacity_permit', permit)
    workflow = WorkflowLoader(Path(__file__).parents[2]/'worker/workflows').load('alpha-method-design')
    started = datetime.now(timezone.utc)
    result = await AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda: 1000).execute(
        task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    stored = SimpleNamespace(id=task.id, input_contract=raw, status='succeeded', started_at=started,
        result={'summary': result.summary})
    verified = verified_method_result(stored)
    state = verified['state']
    if mode == 'capacity':
        assert state['reason'] == 'await_authority_or_capacity'
        assert len(model_calls) == 0 and len(native_calls) == 1
    else:
        assert state['status'] == 'ready_for_independent_review'
        assert len(model_calls) == 1 and len(native_calls) == 2
        assert verified['review_packet']['proposal'] == state['proposal']
        assert 'work_factor_completeness_and_runtime_enforcement' in next(
            v['result']['unverified_obligations'] for v in state['evidence'].values()
            if v.get('schema_version') == 'native-diagnostic-receipt-v1')
        tampered = {k: deepcopy(verified[k]) for k in ['contract_digest', 'state', 'review_packet', 'scientific_approval', 'execution_authority']}
        tampered['schema_version'] = 'method-task-result-v1'
        tampered['state']['proposal']['method']['assurance']['workload']['caps']['statistic_evaluation'] += 1
        tampered['review_packet']['proposal'] = deepcopy(tampered['state']['proposal'])
        tampered['review_packet']['method_episode_digest'] = digest(tampered['state'])
        tampered['result_digest'] = digest(tampered)
        stored.result = {'summary': {'method_episode': tampered}}
        with pytest.raises(ValueError, match='frozen assurance'):
            verified_method_result(stored)
    assert verified['scientific_approval'] is verified['execution_authority'] is False
    assert json.loads((workspace.artifacts/'method-episode-result.json').read_text())['result_digest'] == result.summary['method_episode']['result_digest']
