"""Durable preparation after accepted method review, never execution approval."""
from copy import deepcopy
from math import prod

from sqlalchemy import select

from app.models.task import Task
from app.models.alpha_discovery import AlphaResearchMandate, AlphaDiscoveryCandidate
from app.schemas.alpha_campaign import MethodExecutionPreparationRequest
from app.schemas.task import TaskCreate
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


def verified_preparation_result(task, template):
    """Verify custody and permitted rebinding; native scientific checks stay native."""
    result = task.result or {}
    contract = task.input_contract
    request = contract['released_execution_preparation']
    from app.contracts.research_handoff import decode as decode_handoff
    prepared = decode_handoff(result.get('downstream_handoff') or {}).get('execution_preparation')
    if (task.status != 'succeeded' or result.get('success') is not True
            or result.get('base_commit') != contract['base_ref']
            or result.get('workflow') != 'alpha-research-execution'
            or contract.get('stage') != 'prepare_execution'
            or not isinstance(prepared, dict) or prepared.get('execution_authority') is not False):
        raise ValueError('Successful exact-source preparation receipt required')
    if digest(template) != request['expected_template_digest']:
        raise ValueError('Frozen preparation template changed')
    card = prepared.get('hypothesis_card')
    if (not isinstance(card, dict) or card.get('status') != 'draft'
            or prepared.get('card_digest') != digest(card)
            or card.get('research_question') != ' '.join(contract['question'].split())
            or card.get('engine_hypothesis_template_digest') != contract['reusable_strategy']['contract_digest']
            or card.get('execution_window') != {'start':contract['window_start'], 'end':contract['window_end']}):
        raise ValueError('Prospective card identity mismatch')
    transition = request['representation_transition']
    if prepared.get('representation_transition') != transition:
        raise ValueError('Preparation representation evidence changed')
    grid = template['parameter_grid']
    if not isinstance(grid, dict) or not grid or not all(isinstance(v,list) and v for v in grid.values()):
        raise ValueError('Frozen variant grid invalid')
    variants = prod(len(values) for values in grid.values())
    if variants > contract['max_variants']:
        raise ValueError('Preparation exceeds variant authority')
    original = template['immutable_contract']
    expected = deepcopy(template)
    expected['immutable_contract'].update(source_commit=contract['base_ref'],
        dataset_bindings=deepcopy(request['native_dataset_bindings']),
        validation_requirements=deepcopy(request['validation_requirements']),
        window=deepcopy(request['approved_window']), maximum_variants=variants,
        validation_plans=deepcopy(request['expected_plans']))
    lineage = dict(schema_version='released-execution-contract-binding-v1',
        released_template_digest=digest(template), historical_immutable_contract_digest=digest(original),
        accepted_method_proposal_digest=request['expected_method_digest'],
        prior_source_commit=original.get('source_commit'),source_commit=contract['base_ref'],
        prior_dataset_bindings_digest=digest(original['dataset_bindings']),
        historical_validation_plans_digest=digest(original['validation_plans']),
        dataset_bindings_digest=digest(request['native_dataset_bindings']),
        native_plan_digests={mode:plan['plan_digest'] for mode,plan in request['expected_plans'].items()},
        prepared_contract_digest=digest(expected), requires_independent_execution_review=True,
        execution_authority=False,scientific_certification=False)
    expected_binding = dict(contract=expected,lineage={**lineage,'binding_digest':digest(lineage)})
    if prepared.get('prepared_binding') != expected_binding:
        raise ValueError('Prepared contract or lineage differs from permitted source rebinding')
    return deepcopy(prepared)


def verified_execution_qualification(task, prepared):
    from app.services.alpha_campaign import _qualification_from_result
    result=task.result or {}
    if (task.status!='succeeded' or result.get('success') is not True
            or result.get('base_commit')!=task.input_contract['base_ref']
            or result.get('workflow')!='alpha-research-execution'):
        raise ValueError('Successful source-bound compilation required')
    approval=task.input_contract['card_approval']
    if approval.get('card_digest')!=prepared['card_digest']:
        raise ValueError('Compilation did not use the exact approved card')
    expected_card=deepcopy(prepared['hypothesis_card'])
    expected_card.update(status='confirmed',confirmed_by=approval['actor'],confirmed_at=approval['approved_at'])
    for field in ('claim','entry','exit'):
        expected_card['field_provenance'][field]['state']='confirmed'
    qualification=_qualification_from_result(result)
    if not isinstance(qualification,dict):
        raise ValueError('Compiled qualification missing')
    bundle=qualification.get('artifact_bundle') or {}
    review=qualification.get('review') or {}
    gates=review.get('gates') or {}
    required={'schema_valid','causality_valid','strategy_compilable','leakage_review_passed','auxiliary_joins_backward','independent_review_complete'}
    if (qualification.get('card')!=expected_card or qualification.get('card_digest')!=digest(expected_card)
            or qualification.get('qualification_scope')!='released_execution_compilation_only'
            or 'governed_review' in qualification
            or bundle.get('engine_hypothesis_yaml')!=prepared['prepared_binding']['contract']
            or bundle.get('released_execution_binding')!=prepared['prepared_binding']['lineage']
            or bundle.get('representation_transition')!=prepared['representation_transition']
            or review.get('card_digest')!=digest(expected_card)
            or review.get('review_digest')!=digest({k:v for k,v in review.items() if k!='review_digest'})
            or review.get('blockers')!=[] or set(gates)!=required
            or gates.get('independent_review_complete') is not False
            or any(value is not True for key,value in gates.items() if key!='independent_review_complete')):
        raise ValueError('Compilation differs from approved artifact or deterministic gates')
    return deepcopy(qualification)


def route_execution_review(db,campaign,method_task,preparation,task,prepared,request):
    from uuid import UUID
    from app.models.evaluator_routing import EvaluationRoute
    from app.schemas.evaluator_routing import EvaluationRouteCreate,ProducerIdentity
    from app.services.evaluator_routing import (task_producer_identity,create_route,retry_blocked_route,
        validated_alpha_strategy_reviews,alpha_strategy_reviews_approved,require_independence)
    from app.services.alpha_campaign import (_materialize_strategy_review_tasks,
        _supersede_stale_strategy_review_route,_supersede_failed_strategy_review_route,_complete_independent_qualification)

    qualification=verified_execution_qualification(task,prepared)
    producers=[method_task,task,db.get(Task,UUID(request['engineering_task_id'])),
               db.get(Task,UUID(request['feasibility_task_id'])),preparation]
    identities=[]
    for producer in producers:
        identity=task_producer_identity(db,producer) if producer is not None else None
        if identity is None:
            raise ValueError('Execution review producer provenance missing')
        if len(identities)<2 or identity not in identities:
            identities.append(identity)
    subject=dict(campaign_digest=campaign.campaign_digest,question_digest=task.input_contract['question_digest'],
        source_commit=task.input_contract['base_ref'],qualification_task_id=str(task.id),
        card_digest=digest(qualification['card']),artifact_bundle_digest=digest(qualification['artifact_bundle']),
        producer_agent_ids=sorted({item['agent_id'] for item in identities}),producer_identities=identities,
        qualifier_identity=identities[1])
    subject_digest=digest(subject)
    route=db.scalar(select(EvaluationRoute).where(EvaluationRoute.subject_type=='alpha_strategy_qualification',
        EvaluationRoute.subject_id==str(task.id),EvaluationRoute.subject_digest==subject_digest)
        .order_by(EvaluationRoute.created_at.desc()).limit(1))
    if route is None:
        actors=[ProducerIdentity(actor=item['agent_id'],**item) for item in identities]
        route=create_route(db,EvaluationRouteCreate(subject_type='alpha_strategy_qualification',subject_id=str(task.id),
            subject_digest=subject_digest,producer=actors[1],excluded_producers=actors,
            required_review_kinds=['strategy_spec','causality_leakage'],requested_by='alpha-campaign-director'))
    elif route.status=='assigned':
        route=_supersede_stale_strategy_review_route(db,route,subject)
        route=_supersede_failed_strategy_review_route(db,route,subject)
    elif route.status=='blocked':
        route=retry_blocked_route(db,route)
    _materialize_strategy_review_tasks(db,route,subject,qualification)
    arguments=dict(subject_digest=subject_digest,producer_agent_id=UUID(identities[1]['agent_id']),
        excluded_agent_ids=[UUID(item) for item in subject['producer_agent_ids']],
        excluded_identities=identities,qualifier_identity=identities[1])
    reviews=validated_alpha_strategy_reviews(db,route,**arguments)
    campaign.phase='independent_strategy_review'
    if route.status=='completed' and reviews is None:
        campaign.status='needs_attention'
        campaign.next_action='repair_execution_review_evidence'
        campaign.terminal_reason={'category':'independent_execution_review_invalid','route_id':str(route.id),
            'subject_digest':subject_digest,'qualification_task_id':str(task.id)}
        return None
    if reviews is not None and any(review.verdict!='approve' for review in reviews):
        campaign.status='needs_attention'
        campaign.next_action='repair_prepared_execution_artifact'
        campaign.terminal_reason={'category':'independent_execution_review_rejected','route_id':str(route.id),
            'subject_digest':subject_digest,'qualification_task_id':str(task.id)}
        return None
    if not alpha_strategy_reviews_approved(db,route,**arguments):
        campaign.next_action='await_independent_execution_review'
        campaign.terminal_reason={'category':'independent_execution_review_pending','route_id':str(route.id),
            'subject_digest':subject_digest,'route_status':route.status,'routing_blockers':route.blocked_reason}
        return None
    result=_complete_independent_qualification(qualification,review_route=route,
        independence=require_independence(db,route),subject=subject)
    from app.models.alpha_campaign import AlphaCampaignEvent
    from app.services.alpha_campaign import _append_event
    payload=dict(task_id=str(task.id),route_id=str(route.id),subject_digest=subject_digest,
        qualification_digest=digest(result),execution_authority=False)
    previous=db.scalar(select(AlphaCampaignEvent).where(AlphaCampaignEvent.campaign_id==campaign.id,
        AlphaCampaignEvent.event_type=='execution_qualification_reviewed',
        AlphaCampaignEvent.payload['route_id'].astext==str(route.id)))
    if previous is None:
        _append_event(db,campaign,'execution_qualification_reviewed','alpha-campaign-director',payload)
    elif previous.payload!=payload:
        raise ValueError('Recorded execution review qualification changed')
    campaign.next_action='authorize_reviewed_smoke_execution'
    campaign.terminal_reason={}
    return result


def smoke_contract(compilation, qualification):
    """Use reviewed smoke partitions verbatim; scientific execution is not offered."""
    if (qualification.get('qualified') is not True
            or qualification.get('qualification_scope')!='independently_reviewed_execution'
            or not qualification.get('governed_review')):
        raise ValueError('Independently reviewed execution qualification required')
    native=qualification['artifact_bundle']['engine_hypothesis_yaml']
    plan=native['immutable_contract']['validation_plans']['smoke']
    if (plan.get('mode')!='smoke' or plan.get('status')!='ready' or plan.get('reasons')
            or plan.get('source_commit')!=compilation.input_contract['base_ref']):
        raise ValueError('Ready source-bound smoke plan required')
    contract=deepcopy(compilation.input_contract)
    contract.pop('released_execution_preparation',None)
    contract.pop('card_approval',None)
    contract.update(stage='execute',execution_class='commissioning',qualification=deepcopy(qualification),
        hypothesis_card=deepcopy(qualification['card']),representation_plan=deepcopy(native['representation_plan']),
        validation_plan=deepcopy(plan),window_start=plan['partitions']['smoke']['start'],
        window_end=plan['partitions']['target_tail']['end'],max_variants=qualification['variant_count'])
    if not 1<=contract['max_variants']<=min(8,compilation.input_contract['max_variants']):
        raise ValueError('Smoke variant count exceeds approved bounds')
    return contract


def materialize_reviewed_smoke(db,campaign,compilation,qualification,request):
    if request.get('allow_smoke_execution') is not True:
        return None
    contract=smoke_contract(compilation,qualification)
    number='AEPSMOKE-'+digest({'campaign':str(campaign.id),'parent':str(compilation.id),'contract':contract})[:40]
    task=db.scalar(select(Task).where(Task.task_number==number))
    if task is None:
        task=build_task(TaskCreate(task_number=number,project='bulletproof_bt',task_type='alpha_research_execution',
            title='Approve bounded reviewed native smoke execution',
            objective='Run only the reviewed smoke partition with warmup and target-only tail; retain every variant and terminal evidence.',
            parent_task_id=compilation.id,created_by='alpha-campaign-director',risk_level=1,max_attempts=1,
            approval_required=True,input_contract=contract,
            required_capabilities=['alpha-research-execution','backtesting','research-audit'],allowed_machines=['vm1-developer'],
            expected_outputs=['native smoke outcomes','per-variant artifacts','publication envelope','memory receipts'],
            acceptance_criteria=['No fresh tail decisions','Reviewed native plan','No scientific certification or capital authority'],
            approval_policy={**compilation.approval_policy,'kind':'accepted_method_smoke_execution'}))
        persist_new_task(db,task)
    elif task.input_contract!=contract or task.parent_task_id!=compilation.id:
        raise ValueError('Reviewed smoke task identity conflict')
    campaign.phase='smoke_execution'
    campaign.next_action={'pending_approval':'approve_reviewed_smoke_execution','succeeded':'publish_smoke_outcome',
        'failed':'repair_smoke_execution','cancelled':'smoke_execution_cancelled'}.get(task.status,'await_reviewed_smoke_execution')
    return task


def reconcile_completed_smoke(db, campaign):
    """Collect authorized outcomes even after the window for new work closes."""
    if not (campaign.specification or {}).get('method_execution_preparation_requests'):
        return False
    tasks = list(db.scalars(select(Task).where(
        Task.status == 'succeeded',
        Task.task_type == 'alpha_research_execution',
        Task.approval_policy['kind'].astext == 'accepted_method_smoke_execution',
        Task.approval_policy['campaign_digest'].astext == campaign.campaign_digest,
    )).all())
    for task in tasks:
        consume_reviewed_smoke(db, campaign, task)
    return bool(tasks)


def consume_reviewed_smoke(db,campaign,task):
    """Publish commissioning evidence without manufacturing a scientific attempt."""
    from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignEvent
    from app.services.alpha_campaign import _publication_envelope_from_result,_append_event
    from app.services.alpha_publication import publish_execution
    db.execute(select(AlphaCampaign.id).where(AlphaCampaign.id==campaign.id).with_for_update())
    result=task.result or {}
    envelope=_publication_envelope_from_result(result)
    contract=task.input_contract
    if (task.status!='succeeded' or result.get('success') is not True
            or contract.get('execution_class')!='commissioning' or contract.get('stage')!='execute'
            or contract.get('campaign_digest')!=campaign.campaign_digest
            or result.get('base_commit')!=contract['base_ref']
            or result.get('summary',{}).get('disposition')!='commissioning_complete'
            or not isinstance(envelope,dict)
            or envelope.get('schema_version')!='alpha003-publication-envelope-v1.0.0'
            or envelope.get('task_id')!=str(task.id)
            or envelope.get('source_commit')!=contract['base_ref']
            or envelope.get('campaign_digest')!=campaign.campaign_digest
            or envelope.get('execution_class')!='commissioning'
            or envelope.get('qualification_authority') is not False):
        raise ValueError('Exact completed commissioning envelope required')
    gates=envelope.get('producer_gate_report') or {}
    if (gates.get('qualification_authority') is not False or gates.get('execution_class')!='commissioning'
            or any(gates.get(key) is not False for key in ('capital_authority','production_eligible','shadow_eligible'))
            or 'commissioning_run_has_no_qualification_authority' not in gates.get('failed_gates',[])):
        raise ValueError('Commissioning publication cannot assert scientific or capital authority')
    identity=dict(task_id=str(task.id),plan_digest=task.plan_digest,envelope_digest=digest(envelope),
                  source_commit=contract['base_ref'],execution_class='commissioning',qualification_authority=False)
    previous=db.scalar(select(AlphaCampaignEvent).where(AlphaCampaignEvent.campaign_id==campaign.id,
        AlphaCampaignEvent.event_type=='smoke_outcome_published',AlphaCampaignEvent.payload['task_id'].astext==str(task.id)))
    if previous is not None:
        if any(previous.payload.get(key)!=value for key,value in identity.items()):
            raise ValueError('Published smoke outcome changed')
        campaign.phase='commissioning_terminal'
        campaign.next_action='smoke_outcome_recorded'
        return previous.payload
    # Existing BT-009 publication verifies the consumed founder execution approval
    # and requires retained artifacts, current projections and memory confirmation.
    publication=publish_execution(db,envelope)
    if (publication.get('bridge_state')!='complete' or publication.get('publication_state')!='complete'
            or publication.get('gate_report',{}).get('shadow_eligible') is not False):
        raise ValueError('Smoke publication has not reached a non-promotable terminal receipt')
    payload={**identity,'publication':publication,'scientific_certification':False}
    _append_event(db,campaign,'smoke_outcome_published','alpha-campaign-director',payload)
    campaign.phase='commissioning_terminal'
    campaign.next_action='smoke_outcome_recorded'
    return payload


def publish_execution_preparation(db, campaign, task, template):
    from app.models.alpha_campaign import AlphaCampaignEvent
    from app.services.alpha_campaign import _append_event
    prepared = verified_preparation_result(task, template)
    payload = dict(task_id=str(task.id),plan_digest=task.plan_digest,
        preparation_digest=digest(prepared),card_digest=prepared['card_digest'],
        binding_digest=prepared['prepared_binding']['lineage']['binding_digest'],
        source_commit=task.input_contract['base_ref'],execution_authority=False)
    previous = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id==campaign.id,
        AlphaCampaignEvent.event_type=='execution_preparation_published',
        AlphaCampaignEvent.payload['task_id'].astext==str(task.id)))
    if previous is None:
        _append_event(db,campaign,'execution_preparation_published','alpha-campaign-director',payload)
    elif previous.payload != payload:
        raise ValueError('Published execution preparation changed')
    return prepared


def advance_prepared_card(db, campaign, method_task, preparation, prepared):
    """Bind card confirmation and deterministic compilation, not execution review."""
    from datetime import datetime, timezone
    from app.models.governance import TaskApproval
    from app.services.governance import consume_task_approval
    from app.services.tasks import append_task_event

    number='AEPC-'+digest({'campaign':str(campaign.id),'parent':str(preparation.id),'prepared':prepared})[:40]
    confirmation_contract=deepcopy(preparation.input_contract)
    confirmation_contract.pop('released_execution_preparation')
    confirmation_contract.update(stage='draft',hypothesis_card=deepcopy(prepared['hypothesis_card']))
    confirmation_contract['research_context']['prepared_execution_evidence']=deepcopy(prepared)
    confirmation=db.scalar(select(Task).where(Task.task_number==number))
    if confirmation is None:
        confirmation=build_task(TaskCreate(task_number=number,project='bulletproof_bt',task_type='alpha_research_execution',
            title='Approve exact prepared execution card and retained evidence',
            objective='Confirm this prospective card and evidence before deterministic compilation; no market-data execution.',
            parent_task_id=preparation.id,created_by='alpha-campaign-director',risk_level=0,max_attempts=1,
            approval_required=True,input_contract=confirmation_contract,required_capabilities=['founder-confirmation'],
            allowed_machines=['vm1-developer'],expected_outputs=['exact card approval'],
            acceptance_criteria=['Exact prepared card and evidence','No execution or promotion authority'],
            approval_policy={**preparation.approval_policy,'kind':'accepted_method_execution_card_confirmation'}))
        persist_new_task(db,confirmation)
    elif confirmation.input_contract!=confirmation_contract or confirmation.parent_task_id!=preparation.id:
        raise ValueError('Prepared card confirmation identity conflict')
    campaign.phase='hypothesis_approval'
    campaign.next_action='approve_prepared_execution_card'
    if confirmation.status in {'failed','cancelled'}:
        campaign.next_action='prepared_card_confirmation_'+confirmation.status
        return confirmation
    if confirmation.status!='succeeded':
        approval=db.scalar(select(TaskApproval).where(TaskApproval.task_id==confirmation.id).with_for_update())
        if approval is None or approval.status!='approved':
            return confirmation
        if approval.plan_digest!=confirmation.plan_digest:
            raise ValueError('Prepared card approval plan mismatch')
        completed_at=datetime.now(timezone.utc)
        consume_task_approval(db,confirmation,completed_at)
        confirmation.status='succeeded'
        confirmation.completed_at=completed_at
        confirmation.result={'summary':dict(card_digest=prepared['card_digest'],
            preparation_digest=digest(prepared),approved_by=approval.decided_by,
            approved_at=approval.issued_at.isoformat(),plan_digest=approval.plan_digest)}
        append_task_event(db,confirmation,'task_succeeded','Founder confirmed the exact prepared execution card.',
                          payload=confirmation.result['summary'])
    approved=confirmation.result['summary']
    if (approved.get('card_digest')!=prepared['card_digest'] or approved.get('preparation_digest')!=digest(prepared)
            or approved.get('plan_digest')!=confirmation.plan_digest):
        raise ValueError('Prepared card approval evidence mismatch')
    contract=deepcopy(preparation.input_contract)
    contract['card_approval']=dict(actor=approved['approved_by'],approved_at=approved['approved_at'],
        card_digest=prepared['card_digest'],plan_digest=approved['plan_digest'])
    number='AEPQ-'+digest({'campaign':str(campaign.id),'parent':str(confirmation.id),'contract':contract})[:40]
    task=db.scalar(select(Task).where(Task.task_number==number))
    if task is None:
        task=build_task(TaskCreate(task_number=number,project='bulletproof_bt',task_type='alpha_research_execution',
            title='Compile exact approved execution artifact for independent review',
            objective='Compile the exact approved card and retain all binding evidence; no backtest or paid authoring.',
            parent_task_id=confirmation.id,created_by='alpha-campaign-director',risk_level=0,max_attempts=1,
            approval_required=False,input_contract=contract,
            required_capabilities=['alpha-research-execution','backtesting','research-audit'],allowed_machines=['vm1-developer'],
            expected_outputs=['exact execution qualification for independent review'],
            acceptance_criteria=['Exact approved card','Retained lineage','Independent review remains mandatory'],
            approval_policy=deepcopy(preparation.approval_policy)))
        persist_new_task(db,task)
    elif task.input_contract!=contract or task.parent_task_id!=confirmation.id:
        raise ValueError('Prepared qualification identity conflict')
    campaign.phase='strategy_qualification'
    campaign.next_action={
        'succeeded':'review_prepared_execution_artifact',
        'failed':'prepared_execution_qualification_failed',
        'cancelled':'prepared_execution_qualification_cancelled',
    }.get(task.status,'await_prepared_execution_qualification')
    return task


def preparation_contract(db, campaign, source, method_task, packet, request):
    from app.contracts.engineering_evidence import decode_engineering_evidence
    from app.contracts.representation_transition import representation_transition_evidence
    from app.services.alpha_campaign import _stage_contract
    from app.services.alpha_requirements_feasibility import verified_report

    engineering = db.get(Task, request.engineering_task_id)
    if (engineering is None or engineering.task_type != 'engineering_mission'
            or engineering.status != 'succeeded' or not (engineering.result or {}).get('success')):
        raise ValueError('Successful retained engineering evidence required')
    receipt = engineering.result.get('summary', {}).get('accepted_method_native_handoff', {})
    if (receipt.get('schema_version') != 'accepted-method-native-handoff-v1'
            or receipt.get('receipt_digest') != request.engineering_receipt_digest
            or receipt.get('receipt_digest') != digest({k:v for k,v in receipt.items() if k != 'receipt_digest'})
            or receipt.get('source_commit') != engineering.input_contract.get('base_ref')
            or receipt.get('contract_digest') != digest(engineering.input_contract)
            or receipt.get('execution_authority') is not False):
        raise ValueError('Engineering receipt custody mismatch')
    handoff = decode_engineering_evidence(engineering.input_contract['evidence_context'])['accepted_method_handoff']
    if (receipt.get('packet_digest') != digest(handoff['packet'])
            or receipt.get('accepted_method_digest') != handoff.get('handoff_digest')
            or handoff['packet']['proposal'] != packet['proposal']):
        raise ValueError('Released engineering does not implement this accepted method')
    planning = db.get(Task, request.feasibility_task_id)
    if (planning is None or planning.status != 'succeeded' or planning.task_type != 'alpha_data_admission'
            or planning.input_contract.get('base_ref') != packet['source_commit']):
        raise ValueError('Current-source successful native planning required')
    inputs = planning.input_contract['feasibility_evidence']
    candidate = db.get(AlphaDiscoveryCandidate, method_task.input_contract['candidate_id'])
    if (candidate is None or candidate.candidate_digest != method_task.input_contract['candidate_digest']
            or inputs['discovery_candidate'] != candidate.document):
        raise ValueError('Native preparation candidate custody mismatch')
    report = verified_report(planning, inputs, packet['source_commit'])
    if (report['status'] != 'ready' or report['reasons'] or digest(report) != request.plan_evidence_digest
            or packet['evidence'].get(request.plan_evidence_digest) != report):
        raise ValueError('Exact independently reviewed ready native plans required')
    mandate = db.get(AlphaResearchMandate, method_task.input_contract['mandate_id'])
    catalog = mandate.specification.get('strategy_catalog') or {}
    capabilities = [item for item in catalog.get('capabilities', []) if item['contract_path'] == request.contract_path]
    if catalog.get('source_commit') != packet['source_commit'] or len(capabilities) != 1:
        raise ValueError('Released strategy missing from source-bound mandate catalog')
    template = request.released_template
    if template.get('immutable_contract', {}).get('accepted_method_proposal_digest') != digest(packet['proposal']):
        raise ValueError('Released template method identity mismatch')
    transition = representation_transition_evidence(inputs['representation_plan'], template['representation_plan'],
        accepted_digest=digest(inputs['representation_plan']), released_digest=digest(template['representation_plan']),
        release_source_commit=packet['source_commit'], engineering_bundle_digest=receipt['bundle_digest'])
    ancestor = method_task
    seen = set()
    for _ in range(32):
        if ancestor.id in seen:
            raise ValueError('Method preparation ancestry cycle')
        seen.add(ancestor.id)
        ancestor = db.get(Task, ancestor.parent_task_id)
        if ancestor is None:
            raise ValueError('Original draft context missing')
        if ancestor.task_type == 'alpha_research_execution' and ancestor.input_contract.get('stage') == 'draft':
            break
    else:
        raise ValueError('Method preparation ancestry exceeds bound')
    if ancestor.input_contract['question_digest'] != digest({'question':' '.join(source['question'].split())}):
        raise ValueError('Original draft question differs from preparation')
    contract = _stage_contract(db, campaign, source, stage='prepare_execution',
                               research_context=ancestor.input_contract['research_context'])
    if (len(contract['dataset_bindings']) != len(inputs['dataset_bindings'])
            or any(any(key != 'dataset_path' and bound.get(key) != value for key,value in native.items())
                   for bound,native in zip(contract['dataset_bindings'],inputs['dataset_bindings'],strict=True))):
        raise ValueError('Prepared transport differs from reviewed native dataset identities')
    if (contract['base_ref'] != packet['source_commit'] or contract['representation_plan'] != inputs['representation_plan']
            or contract['question_digest'] != digest({'question':' '.join(source['question'].split())})):
        raise ValueError('Preparation source or representation differs from reviewed method')
    # The native worker independently verifies the exact released YAML bytes,
    # template hash, operational projection and frozen partition instants.
    contract['reusable_strategy'] = deepcopy(capabilities[0])
    contract['released_execution_preparation'] = dict(schema_version='released-execution-preparation-v1',
        expected_template_digest=digest(template), expected_method_digest=digest(packet['proposal']),
        engineering_bundle_digest=receipt['bundle_digest'], accepted_representation=deepcopy(inputs['representation_plan']),
        representation_transition=transition, native_dataset_bindings=deepcopy(inputs['dataset_bindings']),
        validation_requirements=deepcopy(inputs['validation_requirements']), approved_window=deepcopy(inputs['window']),
        expected_plans=deepcopy(report['validation_plans']))
    return contract


def materialize_execution_preparation(db, campaign, source, method_task, packet, identity, route, raw_request):
    from app.services.alpha_method_tasks import require_current_method_authority, route_method_review
    from app.services.evaluator_routing import require_independence
    from app.models.alpha_campaign import AlphaCampaign

    db.execute(select(AlphaCampaign.id).where(AlphaCampaign.id == campaign.id).with_for_update())
    require_current_method_authority(db, method_task)
    request = MethodExecutionPreparationRequest.model_validate(raw_request)
    candidate_id = method_task.input_contract['candidate_id']
    if (campaign.specification.get('method_execution_preparation_requests') or {}).get(candidate_id) != request.model_dump(mode='json'):
        raise ValueError('Preparation differs from exact frozen campaign authority')
    current, reviews = route_method_review(db, campaign, method_task, packet, identity)
    if current.id != route.id or reviews is None or any(review.verdict != 'approve' for review in reviews):
        raise ValueError('Current independent method acceptance required')
    require_independence(db, route)
    contract = preparation_contract(db, campaign, source, method_task, packet, request)
    number = 'AEPREP-' + digest({'campaign':str(campaign.id), 'parent':str(method_task.id), 'contract':contract})[:40]
    existing = db.scalar(select(Task).where(Task.task_number == number))
    if existing is not None:
        if existing.input_contract != contract or existing.parent_task_id != method_task.id:
            raise ValueError('Execution preparation identity conflict')
        return existing
    task = build_task(TaskCreate(task_number=number, project='bulletproof_bt', task_type='alpha_research_execution',
        title='Prepare released execution artifact for exact review',
        objective='Compile the released implementation and retained method into a prospective artifact; no backtest or model calls.',
        parent_task_id=method_task.id, created_by='alpha-campaign-director', risk_level=0, max_attempts=1,
        approval_required=True, input_contract=contract,
        required_capabilities=['alpha-research-execution','backtesting','research-audit'], allowed_machines=['vm1-developer'],
        expected_outputs=['prospective card','source-bound contract','retained lineage'],
        acceptance_criteria=['Exact source, method and dataset identities','No execution authority','Immutable historical evidence'],
        approval_policy={'kind':'accepted_method_execution_preparation','campaign_digest':campaign.campaign_digest,
                         'method_task_id':str(method_task.id), 'request_digest':digest(request.model_dump(mode='json'))}))
    persist_new_task(db, task)
    return task
