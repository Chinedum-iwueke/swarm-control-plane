from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_worker.engineering_episode import canonical_digest as digest
from swarm_worker.executors.alpha_method_design import AlphaMethodDesignExecutor
from swarm_worker.method_task import MethodTaskContract
from swarm_worker.workflows import WorkflowLoader
from test_engineering_episode_executor import fixture


def contract(source):
    evidence = {'kind': 'synthetic_test_assumption', 'not_market_evidence': True}
    return dict(repository='bulletproof_bt', workflow='alpha-method-design', base_ref=source,
        candidate_id=str(uuid4()), candidate_digest='a'*64,
        mandate_id=str(uuid4()), mandate_digest='b'*64,
        valid_until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        proposal={'scientific_identity': {'question': 'frozen synthetic question'},
            'support_minima': {'rows': 100}, 'method': {
                'schema_version': 'design-adequacy-contract-v1', 'estimand': 'synthetic contrast',
                'estimator_id': 'fixture', 'meaningful_effect': {'value': .25, 'units': 'SD',
                    'justification': 'synthetic only', 'evidence_digests': [digest(evidence)]},
                'dependence_assumptions': 'fixture', 'multiplicity': 'single',
                'eligibility_policy': 'frozen', 'undefined_replicate_policy': 'invalidate',
                'calibration': {'seed': 42, 'outer_replicates': 100, 'inner_replicates': 199,
                                'max_work_units': 100000, 'dgp_ids': ['null_iid']}}},
        requirements={'design': 'Complete design, then independent review and calibration'},
        evidence_catalog={digest(evidence): evidence}, dependencies={'admission': 'c'*64},
        findings_digest='d'*64, policy={'allowed_method_fields': ['dependence_assumptions']},
        diagnostic='design_adequacy_v1', authority='method_design_no_execution')


@pytest.mark.asyncio
async def test_fixed_executor_retains_native_packet_and_duplicate_is_free(tmp_path, monkeypatch):
    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    task.input_contract = contract(workspace.metadata.resolved_base_commit)
    task.task_type = 'alpha_method_design'
    workflow = WorkflowLoader(Path(__file__).parents[1]/'workflows').load('alpha-method-design')
    calls, progress = [], []

    async def native(self, **kwargs):
        calls.append(kwargs)
        return {'schema_version': 'native-diagnostic-receipt-v1',
                'result': {'status': 'requires_independent_review_and_native_calibration'},
                'execution_authority': False}

    async def heartbeat(value):
        progress.append(value)

    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.NativeDiagnosticClient.run', native)
    executor = AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda: 1000)
    for _ in range(2):
        result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
        assert result.success
        document = result.summary['method_episode']
        assert document['state']['status'] == 'ready_for_independent_review'
        assert document['schema_version'] == 'method-task-result-v2'
        assert document['review_packet']['method_episode_digest'] == document['audit_state_digest']
        assert document['execution_authority'] is False
        assert document['state']['model_calls'] == 0
        evidence = document['review_packet']['evidence']
        assert set(evidence) == set(document['state']['evidence'])
        assert document['state_evidence_envelopes']
        assert set(task.input_contract['evidence_catalog']) <= set(evidence)
        assert any(v.get('schema_version') == 'native-diagnostic-receipt-v1'
                   for v in evidence.values())
    assert len(calls) == 1
    assert progress[-1]['status'] == 'ready_for_independent_review'
    assert (workspace.artifacts/'method-episode-result.json').exists()


@pytest.mark.asyncio
async def test_expired_method_authority_never_calls_native(tmp_path, monkeypatch):
    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    task.input_contract = contract(workspace.metadata.resolved_base_commit)
    task.input_contract['valid_until'] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    workflow = WorkflowLoader(Path(__file__).parents[1]/'workflows').load('alpha-method-design')
    async def native(*_, **__):
        pytest.fail('expired authority must not execute diagnostics')
    async def heartbeat(_):
        pass
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.NativeDiagnosticClient.run', native)
    result = await AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda: 1000).execute(
        task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert result.summary['method_episode']['state']['reason'] == 'authority'
    assert 'review_packet' not in result.summary['method_episode']


@pytest.mark.asyncio
async def test_known_quota_before_correction_reserves_no_model_calls(tmp_path, monkeypatch):
    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    task.input_contract = contract(workspace.metadata.resolved_base_commit)
    del task.input_contract['proposal']['method']['dependence_assumptions']
    workflow = WorkflowLoader(Path(__file__).parents[1]/'workflows').load('alpha-method-design')
    async def permit():
        return {'allowed': False, 'recovery_token': 'codex:1:open'}
    async def heartbeat(_):
        pass
    async def paid(**_):
        pytest.fail('known quota must not call a model')
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.model_capacity_permit', permit)
    engineering._run_codex = paid
    executor = AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda: 1000)
    for _ in range(2):
        result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
        assert result.termination_reason == 'provider_capacity'
        state = result.summary['method_episode']['state']
        assert state['model_calls'] == 0
        assert state['tool_calls'] == 1
        assert 'review_packet' not in result.summary['method_episode']


@pytest.mark.parametrize('field', ['estimand', 'schema_version', 'scientific_identity', 'experiment'])
def test_method_contract_cannot_authorize_identity_repair(field):
    value = contract('f'*40)
    value['policy']['allowed_method_fields'] = [field]
    with pytest.raises(ValueError, match='repair scope'):
        MethodTaskContract.model_validate(value)


@pytest.mark.asyncio
@pytest.mark.parametrize('repairable', [True, False])
async def test_consistency_findings_repair_in_same_episode_before_review(tmp_path, monkeypatch, repairable):
    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    task.input_contract = contract(workspace.metadata.resolved_base_commit)
    frozen = {'registered_experiment': 'synthetic fixture; native shape mocked here'}
    task.input_contract['proposal']['method'].update(experiment=frozen, calibration_design={})
    task.input_contract['policy']['allowed_method_fields'] = ['calibration_design']
    workflow = WorkflowLoader(Path(__file__).parents[1]/'workflows').load('alpha-method-design')
    calls = []
    async def native(self, **kwargs):
        calls.append('native')
        assert kwargs['payload']['experiment'] == frozen
        repaired = bool(kwargs['payload']['calibration_design'])
        return {'schema_version': 'native-diagnostic-receipt-v1', 'result': {
            'status': 'requires_independent_review_and_native_calibration' if repaired else 'requires_method_correction',
            'consistency': {'status': 'structurally_consistent' if repaired else 'repair_required',
                'finding_count': 0 if repaired else 1,
                'findings': [] if repaired else [dict(code='family_mismatch',
                path='scenarios.null.families', message='Cover every frozen variant jointly',
                disposition='repair' if repairable else 'requires_new_contract')]}}}
    def proposer(*_, **__):
        async def correct(context, operation, remaining):
            assert repairable, 'invalid frozen experiments must not spend author calls'
            calls.append('model')
            assert context['findings'][0]['requirement_ref'] == 'calibration_consistency.family_mismatch'
            return dict(changes={'calibration_design': {'synthetic_corrected_fixture': True}},
                        addressed_findings=context['finding_digests'], rationale='Retain the frozen experiment.')
        return correct
    async def heartbeat(_): pass
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.NativeDiagnosticClient.run', native)
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.correction_proposer', proposer)
    executor = AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda:1000)
    for _ in range(2):
        result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
        state = result.summary['method_episode']['state']
        assert state['status'] == ('ready_for_independent_review' if repairable else 'deferred')
        assert result.summary['method_episode']['scientific_approval'] is False
    assert calls == (['native', 'model', 'native'] if repairable else ['native'])


def test_method_role_and_workflow_are_digest_verified():
    from swarm_worker.role_package import load_role_package
    root = Path(__file__).parents[1]
    package = load_role_package(root/'role-packages/alpha-method-designer/manifest.yaml', root/'workflows')
    assert package.manifest.task_types == ['alpha_method_design']
    assert package.manifest.risk_ceiling == 0
    assert package.manifest.required_capabilities == ['alpha-method-design']


@pytest.mark.asyncio
async def test_review_successor_repairs_once_then_requires_fresh_review(tmp_path, monkeypatch):
    engineering, task, _, workspace = fixture(tmp_path, '1', 1)
    task.input_contract = contract(workspace.metadata.resolved_base_commit)
    report = dict(schema_version='method-review-correction-v1',
        proposal_digest=digest(task.input_contract['proposal']), reviews=[{'method_verdict': {
            'findings': [dict(criterion='design', violation='State dependence precisely',
                             verification='Check the assumption against the design')]} }])
    task.input_contract['findings_digest'] = digest(report)
    task.input_contract['evidence_catalog'][digest(report)] = report
    workflow = WorkflowLoader(Path(__file__).parents[1]/'workflows').load('alpha-method-design')
    calls = []
    def proposer(*_, **__):
        async def correct(context, operation, remaining):
            calls.append('model')
            assert context['findings'][0]['message'] == 'State dependence precisely'
            return dict(changes={'dependence_assumptions': 'Explicit synthetic IID assumption'},
                        addressed_findings=context['finding_digests'], rationale='Synthetic fixture correction.')
        return correct
    async def native(self, **kwargs):
        calls.append('native')
        assert kwargs['payload']['dependence_assumptions'] == 'Explicit synthetic IID assumption'
        return {'schema_version': 'native-diagnostic-receipt-v1',
                'result': {'status': 'requires_independent_review_and_native_calibration'}}
    async def heartbeat(_):
        pass
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.correction_proposer', proposer)
    monkeypatch.setattr('swarm_worker.executors.alpha_method_design.NativeDiagnosticClient.run', native)
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    executor = AlphaMethodDesignExecutor(engineering, python=Path('/unused'), effective_uid=lambda: 1000)
    for _ in range(2):
        result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
        state = result.summary['method_episode']['state']
        assert state['status'] == 'ready_for_independent_review'
        assert state['repairs'] == state['model_calls'] == 1
        assert state['scientific_approval'] is False
        assert state['proposal']['scientific_identity'] == task.input_contract['proposal']['scientific_identity']
        assert 'review_packet' in result.summary['method_episode']
    assert calls == ['model', 'native']
