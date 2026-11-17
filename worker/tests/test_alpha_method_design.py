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
        assert document['review_packet']['method_episode_digest'] == digest(document['state'])
        assert document['execution_authority'] is False
        assert document['state']['model_calls'] == 0
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


@pytest.mark.parametrize('field', ['estimand', 'schema_version', 'scientific_identity'])
def test_method_contract_cannot_authorize_identity_repair(field):
    value = contract('f'*40)
    value['policy']['allowed_method_fields'] = [field]
    with pytest.raises(ValueError, match='repair scope'):
        MethodTaskContract.model_validate(value)


def test_method_role_and_workflow_are_digest_verified():
    from swarm_worker.role_package import load_role_package
    root = Path(__file__).parents[1]
    package = load_role_package(root/'role-packages/alpha-method-designer/manifest.yaml', root/'workflows')
    assert package.manifest.task_types == ['alpha_method_design']
    assert package.manifest.risk_ceiling == 0
    assert package.manifest.required_capabilities == ['alpha-method-design']
