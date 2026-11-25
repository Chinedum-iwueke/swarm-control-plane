from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.alpha_campaign import MethodExecutionPreparationRequest
from app.services import alpha_execution_preparation as service
from app.services import alpha_method_tasks, evaluator_routing
from app.services.graph import digest_document as digest


@pytest.fixture
def context(monkeypatch):
    request = MethodExecutionPreparationRequest(feasibility_task_id=uuid4(), plan_evidence_digest='a'*64,
        engineering_task_id=uuid4(), engineering_receipt_digest='b'*64,
        contract_path='research/hypotheses/example.yaml',released_template={'immutable_contract':{}}).model_dump(mode='json')
    candidate = str(uuid4())
    campaign = SimpleNamespace(id=uuid4(),campaign_digest='c'*64,
        specification={'method_execution_preparation_requests':{candidate:deepcopy(request)}})
    parent = SimpleNamespace(id=uuid4(),input_contract={'candidate_id':candidate})
    route = SimpleNamespace(id=uuid4())
    reviews = [SimpleNamespace(verdict='approve'),SimpleNamespace(verdict='approve')]
    contract = {'stage':'prepare_execution','authority':'no_capital','base_ref':'d'*40}
    monkeypatch.setattr(alpha_method_tasks, 'require_current_method_authority', lambda *_:None)
    monkeypatch.setattr(alpha_method_tasks, 'route_method_review', lambda *_:(route,reviews))
    monkeypatch.setattr(evaluator_routing, 'require_independence', lambda *_:None)
    monkeypatch.setattr(service, 'preparation_contract', lambda *_:deepcopy(contract))
    build = MagicMock(side_effect=lambda payload: SimpleNamespace(id=uuid4(),input_contract=payload.input_contract,
        parent_task_id=payload.parent_task_id,status='pending_approval',payload=payload))
    persist = MagicMock()
    monkeypatch.setattr(service,'build_task',build)
    monkeypatch.setattr(service,'persist_new_task',persist)
    db=MagicMock();db.scalar.return_value=None
    return db,campaign,parent,route,reviews,request,contract,build,persist


def materialize(ctx):
    db,campaign,parent,route,_,request,_,_,_=ctx
    return service.materialize_execution_preparation(db,campaign,{},parent,{}, {},route,request)


def test_materialization_is_durable_idempotent_and_still_approval_gated(context):
    db,_,parent,_,_,_,_,build,persist=context
    task=materialize(context)
    assert task.status=='pending_approval'
    assert task.payload.approval_required is True
    assert task.payload.max_attempts==1
    assert task.input_contract['stage']=='prepare_execution'
    assert task.parent_task_id==parent.id
    db.scalar.return_value=task
    assert materialize(context) is task
    assert build.call_count==persist.call_count==1
    assert db.execute.call_count==2


def completed_smoke():
    campaign=SimpleNamespace(id=uuid4(),campaign_digest='c'*64)
    task=SimpleNamespace(id=uuid4(),status='succeeded',plan_digest='d'*64,
        input_contract=dict(stage='execute',execution_class='commissioning',
                            campaign_digest=campaign.campaign_digest,base_ref='a'*40))
    gates=dict(execution_class='commissioning',qualification_authority=False,
        capital_authority=False,production_eligible=False,shadow_eligible=False,
        failed_gates=['commissioning_run_has_no_qualification_authority'])
    envelope=dict(schema_version='alpha003-publication-envelope-v1.0.0',task_id=str(task.id),
        source_commit='a'*40,campaign_digest=campaign.campaign_digest,
        execution_class='commissioning',qualification_authority=False,producer_gate_report=gates)
    task.result=dict(success=True,base_commit='a'*40,summary=dict(disposition='commissioning_complete'))
    return campaign,task,envelope


def test_completed_smoke_collection_does_not_reopen_expired_campaign(monkeypatch):
    campaign,task,_=completed_smoke()
    campaign.status='expired'
    campaign.specification={'method_execution_preparation_requests':{'candidate':{}}}
    db=MagicMock();db.scalars.return_value.all.return_value=[task]
    consume=MagicMock();monkeypatch.setattr(service,'consume_reviewed_smoke',consume)
    assert service.reconcile_completed_smoke(db,campaign) is True
    consume.assert_called_once_with(db,campaign,task)
    assert campaign.status=='expired'
    campaign.specification={}
    db.reset_mock()
    assert service.reconcile_completed_smoke(db,campaign) is False
    db.scalars.assert_not_called()


def test_smoke_publication_is_idempotent_and_not_scientific(monkeypatch):
    from app.services import alpha_campaign,alpha_publication
    campaign,task,envelope=completed_smoke();db=MagicMock();db.scalar.return_value=None
    monkeypatch.setattr(alpha_campaign,'_publication_envelope_from_result',lambda result:envelope)
    publisher=MagicMock(return_value=dict(bridge_state='complete',publication_state='complete',
                                         gate_report=dict(shadow_eligible=False)))
    monkeypatch.setattr(alpha_publication,'publish_execution',publisher)
    events=MagicMock();monkeypatch.setattr(alpha_campaign,'_append_event',events)
    payload=service.consume_reviewed_smoke(db,campaign,task)
    assert payload['scientific_certification'] is False
    assert campaign.next_action=='smoke_outcome_recorded'
    db.scalar.return_value=SimpleNamespace(payload=payload)
    assert service.consume_reviewed_smoke(db,campaign,task)==payload
    assert publisher.call_count==events.call_count==1
    envelope['extra']='changed'
    with pytest.raises(ValueError,match='outcome changed'):
        service.consume_reviewed_smoke(db,campaign,task)


@pytest.mark.parametrize('failure',['source','authority','promotion','incomplete'])
def test_smoke_publication_fails_closed(monkeypatch,failure):
    from app.services import alpha_campaign,alpha_publication
    campaign,task,envelope=completed_smoke();db=MagicMock();db.scalar.return_value=None
    if failure=='source':envelope['source_commit']='b'*40
    elif failure=='authority':envelope['qualification_authority']=True
    elif failure=='promotion':envelope['producer_gate_report']['shadow_eligible']=True
    monkeypatch.setattr(alpha_campaign,'_publication_envelope_from_result',lambda result:envelope)
    publisher=MagicMock(return_value=dict(bridge_state='pending',publication_state='pending'))
    monkeypatch.setattr(alpha_publication,'publish_execution',publisher)
    events=MagicMock();monkeypatch.setattr(alpha_campaign,'_append_event',events)
    with pytest.raises(ValueError):service.consume_reviewed_smoke(db,campaign,task)
    events.assert_not_called()
    assert publisher.call_count==(1 if failure=='incomplete' else 0)


def test_changed_frozen_request_cannot_materialize(context):
    context[5]['engineering_receipt_digest']='f'*64
    with pytest.raises(ValueError,match='frozen campaign authority'):materialize(context)
    context[8].assert_not_called()


def test_rejected_review_cannot_materialize(context):
    context[4][0].verdict='reject'
    with pytest.raises(ValueError,match='method acceptance'):materialize(context)
    context[8].assert_not_called()


def test_existing_task_with_changed_contract_is_not_reused(context):
    task=materialize(context)
    task.input_contract['stage']='execute'
    context[0].scalar.return_value=task
    with pytest.raises(ValueError,match='identity conflict'):materialize(context)
    assert context[8].call_count==1


def test_missing_current_authority_never_materializes(context,monkeypatch):
    def expired(*_):raise ValueError('expired authority')
    monkeypatch.setattr(alpha_method_tasks,'require_current_method_authority',expired)
    with pytest.raises(ValueError,match='expired authority'):materialize(context)
    context[8].assert_not_called()


def completed_preparation():
    template = dict(parameter_grid={'threshold':[1,2]},immutable_contract={
        'source_commit':'a'*40,'dataset_bindings':[{'dataset_digest':'b'*64}],
        'validation_plans':{'smoke':{'plan_digest':'c'*64}},'accepted_method_proposal_digest':'d'*64},
        scientific_target='Preserved scientific target')
    request = dict(expected_template_digest=digest(template),expected_method_digest='d'*64,
        native_dataset_bindings=[{'dataset_digest':'b'*64,'producer_receipt_digest':'e'*64}],
        validation_requirements={'requirements':{'warmup':10}}, approved_window={'start':'x','end':'y'},
        expected_plans={mode:{'plan_digest':symbol*64} for mode,symbol in [('smoke','1'),('scientific','2')]},
        representation_transition={'narrative_changes':[],'execution_authority':False})
    contract = dict(stage='prepare_execution',base_ref='f'*40,question='A retained scientific question',
        window_start='x',window_end='y',max_variants=2,reusable_strategy={'contract_digest':'3'*64},
        released_execution_preparation=request)
    bound = deepcopy(template)
    bound['immutable_contract'].update(source_commit=contract['base_ref'],dataset_bindings=request['native_dataset_bindings'],
        validation_requirements=request['validation_requirements'],window=request['approved_window'],maximum_variants=2,
        validation_plans=request['expected_plans'])
    original=template['immutable_contract']
    lineage=dict(schema_version='released-execution-contract-binding-v1',released_template_digest=digest(template),
        historical_immutable_contract_digest=digest(original),accepted_method_proposal_digest='d'*64,
        prior_source_commit='a'*40,source_commit='f'*40,prior_dataset_bindings_digest=digest(original['dataset_bindings']),
        historical_validation_plans_digest=digest(original['validation_plans']),
        dataset_bindings_digest=digest(request['native_dataset_bindings']),
        native_plan_digests={mode:p['plan_digest'] for mode,p in request['expected_plans'].items()},
        prepared_contract_digest=digest(bound),requires_independent_execution_review=True,
        execution_authority=False,scientific_certification=False)
    card=dict(status='draft',research_question=contract['question'],engine_hypothesis_template_digest='3'*64,
        execution_window={'start':'x','end':'y'})
    prepared=dict(hypothesis_card=card,card_digest=digest(card),prepared_binding={
        'contract':bound,'lineage':{**lineage,'binding_digest':digest(lineage)}},
        representation_transition=deepcopy(request['representation_transition']),execution_authority=False)
    task=SimpleNamespace(id=uuid4(),plan_digest='4'*64,status='succeeded',input_contract=contract,
        result={'success':True,'base_commit':'f'*40,'workflow':'alpha-research-execution',
                'downstream_handoff':{'execution_preparation':prepared}})
    return task,template


def test_preparation_publication_is_immutable_and_idempotent(monkeypatch):
    from app.services import alpha_campaign
    task,template=completed_preparation();db=MagicMock();db.scalar.return_value=None
    campaign=SimpleNamespace(id=uuid4());events=[]
    monkeypatch.setattr(alpha_campaign,'_append_event',lambda *args:events.append(args[-1]))
    result=service.publish_execution_preparation(db,campaign,task,template)
    assert result['execution_authority'] is False
    db.scalar.return_value=SimpleNamespace(payload=events[0])
    assert service.publish_execution_preparation(db,campaign,task,template)==result
    assert len(events)==1
    task.plan_digest='5'*64
    with pytest.raises(ValueError,match='Published execution preparation changed'):
        service.publish_execution_preparation(db,campaign,task,template)


@pytest.mark.parametrize('change',['source','question','science','lineage','approval','transition','failed','variants'])
def test_preparation_publication_rejects_tampered_or_unready_evidence(change):
    task,template=completed_preparation()
    prepared=task.result['downstream_handoff']['execution_preparation']
    if change=='source': task.result['base_commit']='6'*40
    elif change=='question':
        prepared['hypothesis_card']['research_question']='Another scientific question'
        prepared['card_digest']=digest(prepared['hypothesis_card'])
    elif change=='science':
        bound=prepared['prepared_binding'];bound['contract']['scientific_target']='Changed target'
        bound['lineage']['prepared_contract_digest']=digest(bound['contract'])
        bound['lineage']['binding_digest']=digest({k:v for k,v in bound['lineage'].items() if k!='binding_digest'})
    elif change=='lineage': prepared['prepared_binding']['lineage']['prior_source_commit']='6'*40
    elif change=='approval': prepared['execution_authority']=True
    elif change=='transition': prepared['representation_transition']['narrative_changes']=['changed']
    elif change=='failed': task.status='failed'
    else: task.input_contract['max_variants']=1
    with pytest.raises(ValueError):service.verified_preparation_result(task,template)


def test_prepared_card_requires_exact_confirmation_before_compilation(monkeypatch):
    from datetime import datetime,timezone
    from app.services import governance,tasks
    preparation,_=completed_preparation()
    preparation.input_contract['research_context']={'citations':[]}
    preparation.approval_policy={'kind':'accepted_method_execution_preparation','method_task_id':str(uuid4())}
    prepared=service.verified_preparation_result(preparation,completed_preparation()[1])
    campaign=SimpleNamespace(id=uuid4());db=MagicMock();db.scalar.side_effect=[None,None]
    created=[]
    def build(payload):
        task=SimpleNamespace(id=uuid4(),status='pending_approval' if payload.approval_required else 'queued',
            input_contract=payload.input_contract,parent_task_id=payload.parent_task_id,
            plan_digest=digest(payload.input_contract),payload=payload)
        created.append(task)
        return task
    monkeypatch.setattr(service,'build_task',build)
    persist=MagicMock();monkeypatch.setattr(service,'persist_new_task',persist)
    consume=MagicMock();monkeypatch.setattr(governance,'consume_task_approval',consume)
    monkeypatch.setattr(tasks,'append_task_event',lambda *args,**kwargs:None)
    confirmation=service.advance_prepared_card(db,campaign,None,preparation,prepared)
    assert len(created)==1 and confirmation.payload.approval_required
    assert confirmation.payload.required_capabilities==['founder-confirmation']
    assert campaign.next_action=='approve_prepared_execution_card'
    assert confirmation.input_contract['research_context']['prepared_execution_evidence']==prepared
    assert preparation.input_contract['research_context']=={'citations':[]}
    confirmation.status='cancelled'
    db.scalar.side_effect=[confirmation]
    assert service.advance_prepared_card(db,campaign,None,preparation,prepared) is confirmation
    assert campaign.next_action=='prepared_card_confirmation_cancelled'
    consume.assert_not_called()
    confirmation.status='pending_approval'
    approval=SimpleNamespace(status='approved',decided_by='founder-operator',issued_at=datetime.now(timezone.utc),
        plan_digest=confirmation.plan_digest)
    approval.plan_digest='f'*64
    db.scalar.side_effect=[confirmation,approval]
    with pytest.raises(ValueError,match='approval plan mismatch'):
        service.advance_prepared_card(db,campaign,None,preparation,prepared)


    consume.assert_not_called()
    approval.plan_digest=confirmation.plan_digest
    db.scalar.side_effect=[confirmation,approval,None]
    qualification=service.advance_prepared_card(db,campaign,None,preparation,prepared)
    assert qualification.input_contract['stage']=='prepare_execution'
    assert qualification.input_contract['card_approval']['card_digest']==prepared['card_digest']
    assert qualification.input_contract['released_execution_preparation']==preparation.input_contract['released_execution_preparation']
    assert campaign.next_action=='await_prepared_execution_qualification'
    consume.assert_called_once()
    db.scalar.side_effect=[confirmation,qualification]
    assert service.advance_prepared_card(db,campaign,None,preparation,prepared) is qualification
    assert len(created)==2 and persist.call_count==2
    confirmation.result['summary']['card_digest']='f'*64
    db.scalar.side_effect=[confirmation]
    with pytest.raises(ValueError,match='approval evidence mismatch'):
        service.advance_prepared_card(db,campaign,None,preparation,prepared)


def compiled_preparation():
    preparation,_=completed_preparation()
    prepared=deepcopy(preparation.result['downstream_handoff']['execution_preparation'])
    card=prepared['hypothesis_card']
    card['field_provenance']={field:{'state':'recommended'} for field in ('claim','entry','exit')}
    prepared['card_digest']=digest(card)
    approved=deepcopy(card)
    approved.update(status='confirmed',confirmed_by='founder',confirmed_at='2026-11-25T00:00:00Z')
    for field in ('claim','entry','exit'):approved['field_provenance'][field]['state']='confirmed'
    review=dict(card_digest=digest(approved),blockers=[],gates={name:True for name in (
        'schema_valid','causality_valid','strategy_compilable','leakage_review_passed','auxiliary_joins_backward')})
    review['gates']['independent_review_complete']=False
    review['review_digest']=digest(review)
    qualification=dict(card=approved,card_digest=digest(approved),review=review,
        qualification_scope='released_execution_compilation_only',artifact_bundle={
            'engine_hypothesis_yaml':prepared['prepared_binding']['contract'],
            'released_execution_binding':prepared['prepared_binding']['lineage'],
            'representation_transition':prepared['representation_transition']})
    task=SimpleNamespace(id=uuid4(),status='succeeded',input_contract={**preparation.input_contract,
        'question_digest':'a'*64,'card_approval':{'card_digest':prepared['card_digest'],'actor':'founder',
        'approved_at':approved['confirmed_at']}},result={'success':True,'base_commit':'f'*40,
        'workflow':'alpha-research-execution','downstream_handoff':{'qualification':qualification}})
    return preparation,prepared,task,qualification


def test_compilation_retains_exact_approved_science_and_uncompleted_review_gate():
    _,prepared,task,qualification=compiled_preparation()
    result=service.verified_execution_qualification(task,prepared)
    assert result==qualification
    assert result['review']['gates']['independent_review_complete'] is False


@pytest.mark.parametrize('change',['card','contract','lineage','transition','gate','scope','prior_review','approval'])
def test_compilation_rejects_changed_artifacts_and_premature_review(change):
    _,prepared,task,qualification=compiled_preparation()
    if change=='card':
        qualification['card']['research_question']='Different question'
        qualification['card_digest']=digest(qualification['card'])
    elif change=='contract':qualification['artifact_bundle']['engine_hypothesis_yaml']=dict(changed=True)
    elif change=='lineage':qualification['artifact_bundle']['released_execution_binding']={}
    elif change=='transition':qualification['artifact_bundle']['representation_transition']={}
    elif change=='gate':
        qualification['review']['gates']['independent_review_complete']=True
        qualification['review']['review_digest']=digest({k:v for k,v in qualification['review'].items() if k!='review_digest'})
    elif change=='scope':qualification['qualification_scope']='independently_reviewed_execution'
    elif change=='prior_review':qualification['governed_review']={}
    else:task.input_contract['card_approval']['card_digest']='0'*64
    with pytest.raises(ValueError):service.verified_execution_qualification(task,prepared)


@pytest.mark.parametrize('verdict',['pending','reject','approve','invalid'])
def test_execution_review_excludes_all_producers_and_does_not_authorize_execution(monkeypatch,verdict):
    from app.services import alpha_campaign
    preparation,prepared,task,qualification=compiled_preparation()
    method=SimpleNamespace(id=uuid4());engineering=SimpleNamespace(id=uuid4());planning=SimpleNamespace(id=uuid4())
    records={str(t.id):t for t in (method,engineering,planning,preparation,task)}
    identities={key:dict(agent_id=str(uuid4()),machine='vm1-developer',provider='native',model_family='deterministic',
        runtime='test',context_group=key,package_digest='1'*64,profile_digest='2'*64) for key in records}
    db=MagicMock();db.get.side_effect=lambda model,id:records.get(str(id));db.scalar.return_value=None
    campaign=SimpleNamespace(id=uuid4(),campaign_digest='3'*64,status='running')
    route=SimpleNamespace(id=uuid4(),status='completed' if verdict=='invalid' else 'assigned',blocked_reason={})
    created=[]
    monkeypatch.setattr(evaluator_routing,'task_producer_identity',lambda db,t:identities[str(t.id)])
    monkeypatch.setattr(evaluator_routing,'create_route',lambda db,payload:created.append(payload) or route)
    reviews=None if verdict in {'pending','invalid'} else [SimpleNamespace(verdict=verdict)]*2
    monkeypatch.setattr(evaluator_routing,'validated_alpha_strategy_reviews',lambda *args,**kwargs:reviews)
    monkeypatch.setattr(evaluator_routing,'alpha_strategy_reviews_approved',lambda *args,**kwargs:verdict=='approve')
    monkeypatch.setattr(evaluator_routing,'require_independence',lambda *args:SimpleNamespace(receipt_digest='4'*64))
    materialize=MagicMock();monkeypatch.setattr(alpha_campaign,'_materialize_strategy_review_tasks',materialize)
    monkeypatch.setattr(alpha_campaign,'_complete_independent_qualification',lambda q,**kwargs:dict(q,reviewed=True))
    events=[];monkeypatch.setattr(alpha_campaign,'_append_event',lambda *args:events.append(args[-1]))
    result=service.route_execution_review(db,campaign,method,preparation,task,prepared,
        {'engineering_task_id':str(engineering.id),'feasibility_task_id':str(planning.id)})
    assert {str(p.agent_id) for p in created[0].excluded_producers}=={i['agent_id'] for i in identities.values()}
    assert str(created[0].producer.agent_id)==identities[str(task.id)]['agent_id']
    assert created[0].required_review_kinds==['strategy_spec','causality_leakage']
    subject=materialize.call_args.args[2]
    assert subject['artifact_bundle_digest']==digest(qualification['artifact_bundle'])
    if verdict=='approve':
        assert result['reviewed'] is True
        assert events[0]['execution_authority'] is False
        assert campaign.next_action=='authorize_reviewed_smoke_execution'
    else:
        assert result is None and not events
        assert campaign.next_action=={'reject':'repair_prepared_execution_artifact',
            'invalid':'repair_execution_review_evidence','pending':'await_independent_execution_review'}[verdict]


def reviewed_smoke():
    _,_,compilation,qualification=compiled_preparation()
    qualification=deepcopy(qualification)
    qualification.update(qualified=True,qualification_scope='independently_reviewed_execution',
        governed_review={'receipt_digest':'9'*64},variant_count=2)
    native=qualification['artifact_bundle']['engine_hypothesis_yaml']
    native['representation_plan']={'runtime_representation':'exact'}
    native['immutable_contract']['validation_plans']['smoke']={
        'mode':'smoke','status':'ready','reasons':[],'source_commit':compilation.input_contract['base_ref'],
        'partitions':{'smoke':{'start':'2026-04-01T00:00:00Z','end':'2026-04-20T00:00:00Z'},
                      'target_tail':{'start':'2026-04-20T00:00:00Z','end':'2026-04-20T04:00:00Z'}}}
    compilation.approval_policy={'kind':'accepted_method_execution_preparation','method_task_id':str(uuid4())}
    return compilation,qualification


def test_missing_producer_identity_is_explicit_blocker_not_server_error(monkeypatch):
    preparation, prepared, task, _ = compiled_preparation()
    method = SimpleNamespace(id=uuid4())
    campaign = SimpleNamespace(id=uuid4(), status='running')
    db = MagicMock()
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *args:None)
    monkeypatch.setattr(evaluator_routing, 'historical_profile_producer_identity', lambda *args:None)
    from app.services import engineering_producer_recovery
    monkeypatch.setattr(engineering_producer_recovery, 'recovered_episode_identity', lambda *args:None)
    create = MagicMock();monkeypatch.setattr(evaluator_routing, 'create_route', create)
    result = service.route_execution_review(db,campaign,method,preparation,task,prepared,
        {'engineering_task_id':str(uuid4()),'feasibility_task_id':str(uuid4())})
    assert result is None
    assert campaign.next_action == 'restore_execution_producer_identity'
    assert campaign.terminal_reason['producer_task_id'] == str(method.id)
    create.assert_not_called()


def test_smoke_contract_uses_reviewed_partition_and_tail_without_changing_qualification():
    compilation,qualification=reviewed_smoke();before=deepcopy(qualification)
    result=service.smoke_contract(compilation,qualification)
    assert result['execution_class']=='commissioning' and result['stage']=='execute'
    assert result['window_start']=='2026-04-01T00:00:00Z'
    assert result['window_end']=='2026-04-20T04:00:00Z'
    assert result['representation_plan']=={'runtime_representation':'exact'}
    assert 'released_execution_preparation' not in result and 'card_approval' not in result
    assert qualification==before


@pytest.mark.parametrize('failure',['review','source','mode','variants'])
def test_smoke_rejects_unreviewed_or_out_of_scope_inputs(failure):
    compilation,qualification=reviewed_smoke()
    plan=qualification['artifact_bundle']['engine_hypothesis_yaml']['immutable_contract']['validation_plans']['smoke']
    if failure=='review':qualification['qualified']=False
    elif failure=='source':plan['source_commit']='0'*40
    elif failure=='mode':plan['mode']='scientific'
    else:qualification['variant_count']=9
    with pytest.raises(ValueError):service.smoke_contract(compilation,qualification)


def test_smoke_materialization_is_opt_in_approval_gated_and_idempotent(monkeypatch):
    compilation,qualification=reviewed_smoke();db=MagicMock();campaign=SimpleNamespace(id=uuid4())
    assert service.materialize_reviewed_smoke(db,campaign,compilation,qualification,{}) is None
    db.scalar.assert_not_called()
    db.scalar.return_value=None
    build=MagicMock(side_effect=lambda payload:SimpleNamespace(input_contract=payload.input_contract,
        parent_task_id=payload.parent_task_id,status='pending_approval',payload=payload))
    persist=MagicMock();monkeypatch.setattr(service,'build_task',build);monkeypatch.setattr(service,'persist_new_task',persist)
    task=service.materialize_reviewed_smoke(db,campaign,compilation,qualification,{'allow_smoke_execution':True})
    assert task.payload.approval_required and task.payload.risk_level==1 and task.payload.max_attempts==1
    assert campaign.next_action=='approve_reviewed_smoke_execution'
    assert task.payload.approval_policy['kind']=='accepted_method_smoke_execution'
    db.scalar.return_value=task
    assert service.materialize_reviewed_smoke(db,campaign,compilation,qualification,{'allow_smoke_execution':True}) is task
    assert build.call_count==persist.call_count==1
