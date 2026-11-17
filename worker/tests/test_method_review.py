from copy import deepcopy

import pytest

from swarm_worker.engineering_episode import canonical_digest as digest, EpisodeIntegrityError
from swarm_worker.method_episode import MethodCapacityUnavailable
from swarm_worker.method_review import MethodReviewEpisode, ReviewPolicy, method_review_packet


def identity(name):
    return dict(agent_id=name, context_group=name+'-context', profile_digest=digest(name))


def packet():
    evidence = {'kind':'synthetic_native_check', 'lag':1}
    return dict(schema_version='method-review-packet-v1', method_episode_digest='a'*64,
        source_commit='b'*40, proposal={'lag':1}, requirements={'causality':'Use completed bars'},
        prior_requirements={'causality':'Old wording'}, evidence={digest(evidence):evidence},
        dependencies={'dataset':'c'*64})


def verdict(context, reject=False):
    return dict(packet_digest=context['packet_digest'], verdict='reject' if reject else 'accept',
        checks=list(context['packet']['requirements']), rationale='Fixture verdict, not science',
        findings=[dict(criterion='causality', evidence_digests=[next(iter(context['packet']['evidence']))],
            violation='Claims current-bar use', verification='Inspect recorded temporal offset')] if reject else [])


async def approve(kind, who, context, *_): return verdict(context)


async def reject_initial(kind, who, context, *_):
    return verdict(context, reject=not any('finding_digest' in doc for doc in context['packet']['evidence'].values()))


async def counterexamples(context, operation, work, remaining):
    records = {}
    for review in context['reviews'].values():
        for finding in review['verdict']['findings']:
            value = dict(packet_digest=context['packet_digest'], finding_digest=digest(finding),
                criterion=finding['criterion'], outcome='contradicts', operation=operation,
                execution_authority=False, native_receipt='fixture-only')
            records[digest(value)] = value
    return records


async def recheck(who, context, *_):
    return dict(packet_digest=context['packet_digest'], decision='recheck',
        counterevidence_digests=list(context['counterevidence']), rationale='Counterexample needs fresh review')


def episode(tmp_path, **kwargs):
    return MethodReviewEpisode(tmp_path/'reviews', packet=kwargs.pop('packet',packet()),
        producers=kwargs.pop('producers',[identity('author')]),
        reviewers=kwargs.pop('reviewers',{'strategy_spec':identity('spec'),'causality_leakage':identity('causal')}),
        adjudicator=kwargs.pop('adjudicator',identity('judge')),
        policy=kwargs.pop('policy',ReviewPolicy()), review=kwargs.pop('review',approve),
        counterexamples=kwargs.pop('counterexamples',counterexamples),
        adjudicate=kwargs.pop('adjudicate',recheck), current=kwargs.pop('current',lambda _:True),
        verify_counterevidence=kwargs.pop('verify_counterevidence',lambda *_:True), **kwargs)


@pytest.mark.asyncio
async def test_both_reviews_required_and_exact_result_reused(tmp_path):
    calls = []
    async def review(kind, who, context, *_):
        calls.append(kind)
        assert 'reviews' not in context
        assert context['changed_criteria']==['causality']
        return verdict(context)
    engine = episode(tmp_path,review=review)
    state = await engine.run()
    assert state['status']=='review_complete'
    assert calls==['causality_leakage','strategy_spec']
    assert state['scientific_approval'] is state['execution_authority'] is False
    assert await engine.run()==state and len(calls)==2


@pytest.mark.asyncio
async def test_unsupported_finding_requires_fresh_reviews_by_both_unchanged_evaluators(tmp_path):
    engine = episode(tmp_path,review=reject_initial)
    state = await engine.run()
    assert state['status']=='review_complete' and state['model_calls']==5
    assert state['rechecks']==state['tool_calls']==1
    reviews = [h for h in state['history'] if h.get('stage')=='review']
    assert len(reviews)==4
    assert all(r['result']['verdict']['verdict']=='reject' for r in reviews[:2])
    assert all(r['result']['verdict']['verdict']=='accept' for r in reviews[2:])
    assert reviews[0]['packet_digest']!=reviews[2]['packet_digest']
    assert state['packet']['proposal']==packet()['proposal']


@pytest.mark.asyncio
async def test_legitimate_defect_survives_adjudication(tmp_path):
    async def reject(kind, who, context, *_): return verdict(context,True)
    state = await episode(tmp_path,review=reject).run()
    assert state['status']=='rejected' and state['model_calls']==5
    assert state['rechecks']==1


@pytest.mark.parametrize('change', ['producer','context','reviewer','judge'])
def test_independence_is_not_model_asserted(tmp_path,change):
    reviewers={'strategy_spec':identity('spec'),'causality_leakage':identity('causal')}
    judge=identity('judge')
    if change=='producer': reviewers['strategy_spec']=identity('author')
    if change=='context': reviewers['strategy_spec']['context_group']='author-context'
    if change=='reviewer': reviewers['strategy_spec']=identity('causal')
    if change=='judge': judge=identity('spec')
    with pytest.raises(ValueError,match='distinct'):
        episode(tmp_path,reviewers=reviewers,adjudicator=judge)


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['source','dataset','requirements','evidence','profile'])
async def test_changed_bindings_cannot_reuse_old_review(tmp_path,change):
    await episode(tmp_path).run()
    p=packet()
    kwargs={}
    if change=='source': p['source_commit']='e'*40
    if change=='dataset': p['dependencies']['dataset']='e'*64
    if change=='requirements': p['requirements']['causality']='Changed criterion'
    if change=='evidence': p['evidence'][digest({'new':1})]={'new':1}
    if change=='profile': kwargs['adjudicator']={**identity('judge'),'profile_digest':'e'*64}
    with pytest.raises(EpisodeIntegrityError): await episode(tmp_path,packet=p,**kwargs).run()


@pytest.mark.asyncio
async def test_revoked_registration_hides_cached_acceptance_without_erasing_it(tmp_path):
    engine=episode(tmp_path)
    state=await engine.run()
    engine.current=lambda _:False
    assert (await engine.run())['status']=='deferred'
    assert engine.store.load()['status']=='review_complete'


@pytest.mark.asyncio
async def test_mid_review_authority_wait_requires_new_signal(tmp_path):
    calls=[]
    def current(_):
        calls.append(1)
        return len(calls)<3
    engine=episode(tmp_path,current=current)
    state=await engine.run()
    assert state['reason']=='authority_changed' and state['model_calls']==1
    engine.current=lambda _:True
    assert await engine.run()==state
    resumed=await engine.run(recovery_token='authority-renewed')
    assert resumed['status']=='review_complete' and resumed['model_calls']==2


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['criterion','evidence','omission','contradiction','packet'])
async def test_invalid_verdicts_fail_closed_and_are_retained(tmp_path,change):
    async def invalid(kind,who,context,*_):
        result=verdict(context,True)
        if change=='criterion': result['findings'][0]['criterion']='made_up'
        if change=='evidence': result['findings'][0]['evidence_digests']=['unrecorded']
        if change=='omission': result['checks']=['other']
        if change=='contradiction': result['verdict']='accept'
        if change=='packet': result['packet_digest']='e'*64
        return result
    state=await episode(tmp_path,review=invalid).run()
    assert state['status']=='blocked'
    assert state['history'][-1]['status']=='invalid_result'


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['unrelated','hash','custody','supports','inconclusive'])
async def test_counterexample_cannot_launder_unrelated_success(tmp_path,change):
    async def tools(context,*args):
        values=await counterexamples(context,*args)
        doc=deepcopy(next(iter(values.values())))
        if change=='unrelated': doc['criterion']='unrelated'
        if change in {'supports','inconclusive'}: doc['outcome']=change
        return {('f'*64 if change=='hash' else digest(doc)):doc}
    state=await episode(tmp_path,review=reject_initial,counterexamples=tools,
        verify_counterevidence=lambda *_:change!='custody').run()
    assert state['status'] in {'blocked','disputed'}
    assert state['model_calls']==2  # No paid adjudication for deterministically ineligible evidence.


@pytest.mark.asyncio
@pytest.mark.parametrize('decision,refs',[('approve',None),('recheck',[]),('recheck',['invented']),('disputed',[])])
async def test_adjudicator_cannot_approve_or_invent_counterevidence(tmp_path,decision,refs):
    async def judge(who,context,*_):
        return dict(packet_digest=context['packet_digest'],decision=decision,
            counterevidence_digests=refs or [],rationale='Fixture')
    state=await episode(tmp_path,review=reject_initial,adjudicate=judge).run()
    assert state['status'] in {'blocked','disputed'} and state['model_calls']==3


@pytest.mark.asyncio
async def test_interruption_and_quota_do_not_refund_calls(tmp_path):
    async def crash(*_): raise RuntimeError('interrupted')
    engine=episode(tmp_path,review=crash)
    with pytest.raises(RuntimeError): await engine.run()
    assert engine.store.load()['model_calls']==1
    async def quota(*_): raise MethodCapacityUnavailable()
    engine.review=quota
    state=await engine.run()
    assert state['model_calls']==2 and state['reason']=='capacity'
    assert await engine.run()==state
    engine.review=approve
    resumed=await engine.run(recovery_token='probe-1')
    assert resumed['status']=='review_complete' and resumed['model_calls']==4
    assert resumed['deadline']==state['deadline']


@pytest.mark.asyncio
async def test_budgets_stop_review_chasing(tmp_path):
    engine=episode(tmp_path,review=reject_initial,policy=ReviewPolicy(max_model_calls=2))
    state=await engine.run()
    assert state['reason']=='model_budget_exhausted'
    assert (await engine.run(recovery_token='probe'))==state


def test_bridge_only_accepts_ready_method_and_retained_evidence():
    e={'test':1}
    state=dict(status='ready_for_independent_review',scientific_approval=False,execution_authority=False,
        evidence={digest(e):e},proposal={'lag':1},binding={'source_commit':'a'*40})
    p=method_review_packet(state,requirements={'lag':'completed'},evidence=state['evidence'],dependencies={'data':'b'*64})
    assert p['method_episode_digest']==digest(state)
    state['status']='deferred'
    with pytest.raises(EpisodeIntegrityError):
        method_review_packet(state,requirements={},evidence={},dependencies={})


@pytest.mark.asyncio
async def test_deadline_and_locking_survive_restart(tmp_path):
    import asyncio
    async def slow(*_): await asyncio.sleep(2)
    engine=episode(tmp_path,review=slow,policy=ReviewPolicy(duration_seconds=1))
    with engine.store.locked():
        with pytest.raises(EpisodeIntegrityError): await engine.run()
    state=await engine.run()
    assert state['reason']=='deadline_exhausted'
    assert await engine.run(recovery_token='new')==state


@pytest.mark.asyncio
@pytest.mark.parametrize('criterion,observed,required', [('causal_lag',1,1),('history_bars',48,48),('split_gap',12,12)])
async def test_computed_counterexamples_resolve_false_fixture_findings(tmp_path,criterion,observed,required):
    p=packet()
    p['proposal']={criterion:observed}
    p['requirements']={criterion:{'minimum':required}}
    async def reviewer(kind,identity,context,*_):
        receipts=[e for e in context['packet']['evidence'].values() if e.get('criterion')==criterion]
        return dict(packet_digest=context['packet_digest'],verdict='accept' if receipts else 'reject',
            checks=[criterion],rationale='Check the fixture numeric inequality',findings=[] if receipts else [dict(
                criterion=criterion,evidence_digests=[next(iter(context['packet']['evidence']))],
                violation='Alleged insufficient value',verification='Compare observed to frozen minimum')])
    async def tool(context,operation,limit,remaining):
        value=context['packet']['proposal'][criterion]
        minimum=context['packet']['requirements'][criterion]['minimum']
        result={}
        for r in context['reviews'].values():
            for f in r['verdict']['findings']:
                doc=dict(packet_digest=context['packet_digest'],finding_digest=digest(f),criterion=criterion,
                    outcome='contradicts' if value>=minimum else 'supports',execution_authority=False,
                    operation=operation,observed=value,required=minimum)
                result[digest(doc)]=doc
        return result
    def verify(receipt,context,operation,limit):
        return (receipt['operation']==operation and receipt['observed']==observed
                and receipt['required']==required and receipt['observed']>=receipt['required'])
    state=await episode(tmp_path,packet=p,review=reviewer,counterexamples=tool,verify_counterevidence=verify).run()
    assert state['status']=='review_complete' and state['rechecks']==1


@pytest.mark.asyncio
async def test_aep004_checkpoint_connects_to_review_without_granting_execution(tmp_path):
    from test_method_episode import episode as method_episode
    method=await method_episode(tmp_path/'method').run()
    p=method_review_packet(method,requirements={'causality':'Completed bars'},
        evidence=method['evidence'],dependencies={'data':'d'*64})
    review=await episode(tmp_path/'review',packet=p).run()
    assert review['status']=='review_complete'
    assert review['packet']['proposal']==method['proposal']
    assert review['scientific_approval'] is review['execution_authority'] is False
