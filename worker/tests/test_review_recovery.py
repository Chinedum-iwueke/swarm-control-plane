import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from swarm_worker.method_verdict_contract import complete_rejection_summary
from swarm_worker.review_context import canonical, review_context
from swarm_worker.review_evidence import prepare_evidence
from swarm_worker.review_recovery import retained_review
from swarm_worker.strategy_review_contract import AlphaStrategyReviewContract, MethodStrategyReview, review_digest
from test_alpha_strategy_review_executor import contract as base_contract


def fixture(tmp_path):
    payload = base_contract()
    evidence = {'proof': 'retained'}
    key = review_digest(evidence)
    packet = {'requirements': {'one': 'first', 'two': 'second'}, 'evidence': {key: evidence},
              'plan': 'unique' * 19000}
    payload['qualification']['artifact_bundle'] = {'method_review_packet': packet}
    payload['subject'].update(review_scope='method_design', artifact_bundle_digest=review_digest(payload['qualification']['artifact_bundle']))
    payload['subject_digest'] = review_digest(payload['subject'])
    contract = AlphaStrategyReviewContract.model_validate(payload)
    manifest = review_context(contract.model_dump(mode='json'))
    old = tmp_path / 'attempt-1'
    current = tmp_path / 'attempt-2'
    for directory in (old, current):
        (directory / 'artifacts').mkdir(parents=True)
    task = SimpleNamespace(id=uuid4(), attempt_count=2, failure={'detail': 'Method blockers differ from retained findings'})
    (old / 'metadata.json').write_text(json.dumps({'task_id': str(task.id), 'attempt_number': 1,
        'resolved_base_commit': contract.base_ref, 'repository': contract.repository}))
    prepare_evidence(old / 'artifacts', contract.model_dump(mode='json'), manifest)
    raw = {'subject_digest':contract.subject_digest,'verdict':'reject','rationale':'Real retained rejection with explicit findings.',
        'checks':['one','two'],'blockers':['first defect'],
        'method_verdict':{'packet_digest':review_digest(packet),'verdict':'reject','checks':['one','two'],
            'rationale':'Retained independent review findings.', 'findings':[
                {'criterion':criterion,'evidence_digests':[key],'violation':violation,'verification':'Check exact evidence.'}
                for criterion,violation in [('one','first defect'),('two','second defect')]]},
        'evidence_coverage':{'one':[key],'two':[key]}}
    (old / 'artifacts' / 'strategy-review.json').write_text(canonical(raw))
    request={'source_attempt':'attempt-1','contract_digest':review_digest(contract.model_dump(mode='json')),
             'raw_review_digest':review_digest(raw)}
    workspace=SimpleNamespace(plan=SimpleNamespace(attempt_directory=current),artifacts=current/'artifacts')
    return task, workspace, contract, manifest, request, raw


@pytest.mark.parametrize('overflow', [False, True])
def test_retained_rejection_is_completed_without_changing_findings(tmp_path, overflow):
    args=fixture(tmp_path)
    if overflow:
        args[0].failure = {'error_category': 'executor_ValidationError',
            'detail': '1 validation error for WorkflowExecutionResult\n  Value error, execution summary exceeds 16 KiB [type=value_error]'}
    raw=args[-1]
    review,coverage=retained_review(*args[:-1])
    assert review.blockers==['first defect','second defect']
    assert review.method_verdict.model_dump()==raw['method_verdict']
    assert review.verdict=='reject'
    assert coverage==raw['evidence_coverage']
    assert retained_review(*args[:-1])[0]==review


def test_evidence_review_summary_has_a_bounded_transport_allowance():
    from swarm_worker.models import WorkflowExecutionResult
    fields = dict(workflow='alpha-strategy-review', repository='bulletproof_bt',
        base_commit='a'*40, task_attempt=1, total_duration_seconds=0,
        steps=[], success=True, summary={'synthetic': 'x'*20000})
    assert WorkflowExecutionResult(**fields).success
    with pytest.raises(ValueError, match='16 KiB'):
        WorkflowExecutionResult(**(fields | {'workflow':'ordinary'}))
    with pytest.raises(ValueError, match='256 KiB'):
        WorkflowExecutionResult(**(fields | {'summary': {'synthetic': 'x'*262144}}))


@pytest.mark.parametrize('fault',['digest','contract','path','metadata','symlink','evidence','unrelated_failure'])
def test_retained_recovery_fails_closed(tmp_path,fault):
    task,workspace,contract,manifest,request,raw=fixture(tmp_path)
    old=tmp_path/'attempt-1'
    if fault=='digest':request['raw_review_digest']='0'*64
    elif fault=='contract':request['contract_digest']='0'*64
    elif fault=='path':request['source_attempt']='../attempt-1'
    elif fault=='metadata':(old/'metadata.json').write_text('{}')
    elif fault=='symlink':
        path=old/'artifacts'/'strategy-review.json';path.unlink();path.symlink_to('/does-not-exist')
    elif fault=='evidence':
        path=old/'artifacts'/'review-evidence.json';path.chmod(0o600);path.write_text('{}')
    else:task.failure['detail']='Different failure'
    with pytest.raises(ValueError):retained_review(task,workspace,contract,manifest,request)


def test_completion_never_drops_an_unmatched_blocker(tmp_path):
    raw=fixture(tmp_path)[-1]
    raw.pop('evidence_coverage')
    raw['blockers'].append('a different substantive defect')
    with pytest.raises(ValueError,match='changing meaning'):
        complete_rejection_summary(MethodStrategyReview.model_validate(raw))


@pytest.mark.asyncio
async def test_executor_recovery_checks_lease_and_never_calls_model(tmp_path):
    from swarm_worker.executors.alpha_strategy_review import AlphaStrategyReviewExecutor
    task,workspace,contract,manifest,request,raw=fixture(tmp_path)
    task.input_contract=contract.model_dump(mode='json')
    task.assigned_agent_id=contract.evaluator_agent_id
    task.failure['operator_retry_context']={'review_publication_recovery':request}
    task.prior_failure=task.failure
    task.failure={}
    workspace.plan.resolved_base_commit=contract.base_ref
    workflow=SimpleNamespace(name=contract.workflow,steps=[])
    class Runner:
        async def start(self,*args,**kwargs):
            pytest.fail('Publication recovery must not call a model')
    checks=[]
    async def heartbeat(value):checks.append(value)
    executor=AlphaStrategyReviewExecutor(codex_home=tmp_path,codex_model='test',
        heartbeat_interval_seconds=1,process_runner=Runner(),effective_uid=lambda:1000)
    result=await executor.execute(task=task,workflow=workflow,workspace=workspace,heartbeat=heartbeat)
    assert checks and result.success and result.steps==[]
    assert result.summary['publication_recovery']['model_calls']==0
    assert result.summary['alpha_strategy_review']['blockers']==['first defect','second defect']
    async def expired(_):raise RuntimeError('authority expired')
    with pytest.raises(RuntimeError,match='authority expired'):
        await executor.execute(task=task,workflow=workflow,workspace=workspace,heartbeat=expired)
