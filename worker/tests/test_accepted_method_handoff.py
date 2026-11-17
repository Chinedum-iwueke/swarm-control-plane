from copy import deepcopy
import json

import pytest

from swarm_worker.accepted_method_handoff import bind_accepted_method, verify_handoff, bundle_binding
from swarm_worker.engineering_episode import canonical_digest as digest, EpisodeIntegrityError
from swarm_worker.engineering_evidence import decode_engineering_evidence, encode_engineering_evidence
from test_engineering_episode_executor import fixture, step
from test_method_review import episode as review_episode, packet


async def accepted(tmp_path,contract):
    p=packet()
    p['source_commit']=contract.base_ref
    plans={}
    for mode in ('smoke','scientific'):
        plan=dict(schema_version='requirements-aware-validation-plan-v1',mode=mode,
            source_commit=contract.base_ref,status='ready',reasons=[],
            partitions={'test':{'start':'2025-01-01','end':'2025-02-01'}},execution_authority=False)
        plans[mode]=plan|{'plan_digest':digest(plan)}
    report={'validation_plans':plans}
    report_digest=digest(report)
    p['evidence'][report_digest]=report
    state=await review_episode(tmp_path,packet=p).run()
    bound=bind_accepted_method(contract,state,plan_evidence_digest=report_digest,
        registration_receipt={'route_id':'fixture-not-production'},current=lambda *_:True)
    return bound,state,report_digest


@pytest.mark.asyncio
async def test_review_to_contract_is_explicit_and_immutable(tmp_path):
    executor,task,workflow,workspace=fixture(tmp_path/'work','1',1)
    from swarm_worker.policy import EngineeringMissionContract
    original=EngineeringMissionContract.model_validate(task.input_contract)
    bound,state,ref=await accepted(tmp_path/'reviews',original)
    assert original.evidence_context=='{}'
    assert verify_handoff(bound,original.base_ref)['review_state_digest']==digest(state)
    with pytest.raises(EpisodeIntegrityError): verify_handoff(bound,'f'*40)
    with pytest.raises(EpisodeIntegrityError):
        verify_handoff(bound.model_copy(update={'allowed_paths':['unapproved.py']}),original.base_ref)
    with pytest.raises(EpisodeIntegrityError):
        bind_accepted_method(original,state,plan_evidence_digest=ref,
            registration_receipt={'route_id':'x'},current=lambda *_:False)


@pytest.mark.asyncio
@pytest.mark.parametrize('tamper',['review','plan','source','digest','profile'])
async def test_rehashed_invalid_handoffs_fail_closed(tmp_path,tamper):
    _,task,_,_=fixture(tmp_path/'work','1',1)
    from swarm_worker.policy import EngineeringMissionContract
    contract=EngineeringMissionContract.model_validate(task.input_contract)
    bound,_,_=await accepted(tmp_path/'reviews',contract)
    e=decode_engineering_evidence(bound.evidence_context)
    h=e['accepted_method_handoff']
    if tamper=='review': h['reviews']['strategy_spec']['verdict']['verdict']='reject'
    if tamper=='plan': h['plan_evidence_digest']='a'*64
    if tamper=='source': h['packet']['source_commit']='f'*40
    if tamper=='profile': h['reviews']['strategy_spec']['identity']['agent_id']='other'
    if tamper!='digest': h['handoff_digest']=digest({k:v for k,v in h.items() if k!='handoff_digest'})
    else: h['handoff_digest']='f'*64
    bad=bound.model_copy(update={'evidence_context':encode_engineering_evidence(e)})
    with pytest.raises((ValueError,EpisodeIntegrityError)): verify_handoff(bad,contract.base_ref)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['reconstructed','session'])
@pytest.mark.parametrize('expression,expected', [('int(2 >= 2)',1),('sum([2,4,6])/3',4.0),('[10,20,30][:-1]',[10,20])])
async def test_same_repair_cases_and_budgets_reach_bound_bundle(tmp_path,mode,expression,expected,monkeypatch):
    from swarm_worker.policy import EngineeringMissionContract
    monkeypatch.delenv('SWARM_AGENT_TOKEN',raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE','subscription')
    executor,task,workflow,workspace=fixture(tmp_path/'work',expression,expected)
    contract=EngineeringMissionContract.model_validate(task.input_contract).model_copy(update={
        'evidence_context':encode_engineering_evidence({'author_continuity':mode})})
    bound,_,_=await accepted(tmp_path/'reviews',contract)
    task.input_contract=bound.model_dump(mode='json')
    author_calls=[]
    thread='11111111-1111-4111-8111-111111111111'
    async def author(**kwargs):
        author_calls.append(kwargs)
        code='None' if len(author_calls)==1 else expression
        (workspace.repository/'signal_logic.py').write_text(f'def signal():\n    return {code}\n# fixture repair\n')
        (kwargs['workspace'].artifacts/'coder-summary.md').write_text('Synthetic fixture implementation')
        result=step('coding-agent',kwargs['workspace'])
        if mode=='session':
            (kwargs['workspace'].logs/'coding-agent.stdout.log').write_text(json.dumps({'type':'thread.started','thread_id':thread})+'\n')
            assert '--last' not in kwargs['args'] and '--ephemeral' not in kwargs['args']
            if len(author_calls)==2: assert 'resume' in kwargs['args'] and thread in kwargs['args']
        return result
    async def codex(**kwargs):
        if kwargs['name']=='coding-agent': return await author(**kwargs)
        assert '--ephemeral' in kwargs['args'] and thread not in kwargs['args']
        assert thread not in kwargs['prompt']
        (kwargs['workspace'].artifacts/'decision.json').write_text(json.dumps({'approved':True,'summary':'fixture','findings':[]}))
        return step(kwargs['name'],kwargs['workspace'])
    executor._run_author=author
    executor._run_codex=codex
    async def heartbeat(_): pass
    result=await executor.execute(task=task,workflow=workflow,workspace=workspace,heartbeat=heartbeat)
    assert result.success and len(author_calls)==2
    linkage=json.loads((workspace.artifacts/'accepted-method-native-handoff.json').read_text())
    assert set(linkage['stage_receipts'])=={'focused','review','validation','bundle'}
    assert set(linkage['validation_plan_digests'])=={'smoke','scientific'}
    assert linkage['execution_authority'] is linkage['scientific_certification'] is False
    assert result.summary['engineering_episode']['repairs']==1
    state=json.loads((workspace.plan.attempt_directory.parent/'engineering-episode/state.json').read_text())['state']
    h=verify_handoff(bound,bound.base_ref)
    with pytest.raises(EpisodeIntegrityError,match='patch differs'):
        bundle_binding(h,state,contract=bound,patch='different patch',
            bundle=json.loads((workspace.artifacts/'pr-bundle.json').read_text()))
