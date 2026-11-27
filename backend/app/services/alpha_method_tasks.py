"""Idempotent, source-bound method tasks under explicit commissioning authority."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignEvent
from app.models.alpha_discovery import AlphaResearchMandate
from app.models.task import Task
from app.schemas.method_task import MethodTaskContract
from app.schemas.task import TaskCreate
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


def require_current_method_authority(db, task):
    if (task.task_type == 'alpha_research_execution'
            and (task.approval_policy or {}).get('kind') in {
                'accepted_method_execution_preparation', 'accepted_method_execution_card_confirmation',
                'accepted_method_smoke_execution'}):
        from uuid import UUID
        from fastapi import HTTPException
        try:
            parent = db.get(Task, UUID(task.approval_policy['method_task_id']))
            if parent is None or parent.task_type != 'alpha_method_design':
                raise ValueError('missing method parent')
            require_current_method_authority(db, parent)
            packet = verified_method_result(parent)['review_packet']
            campaign = db.scalar(select(AlphaCampaign).where(
                AlphaCampaign.campaign_digest == task.approval_policy['campaign_digest']))
            request = campaign.specification['method_execution_preparation_requests'][parent.input_contract['candidate_id']]
            expected_stage = ('draft' if task.approval_policy['kind']=='accepted_method_execution_card_confirmation'
                              else 'execute' if task.approval_policy['kind']=='accepted_method_smoke_execution'
                              else 'prepare_execution')
            if (task.input_contract['stage'] != expected_stage
                    or task.input_contract['base_ref'] != packet['source_commit']
                    or digest(request) != task.approval_policy['request_digest']):
                raise ValueError('preparation authority changed')
            from app.services.evaluator_routing import task_producer_identity
            identity = task_producer_identity(db, parent)
            if identity is None:
                raise ValueError('method producer missing')
            _, reviews = route_method_review(db, campaign, parent, packet, identity)
            if reviews is None or any(review.verdict != 'approve' for review in reviews):
                raise ValueError('method no longer accepted')
            if expected_stage=='execute':
                from app.models.evaluator_routing import EvaluationRoute
                from app.services.evaluator_routing import require_independence, alpha_strategy_reviews_approved
                qualification=task.input_contract['qualification']
                governed=qualification['governed_review']
                subject=governed['subject']
                route=db.get(EvaluationRoute,UUID(governed['route_id']))
                if (request.get('allow_smoke_execution') is not True
                        or task.input_contract.get('execution_class')!='commissioning'
                        or route is None or route.subject_digest!=digest(subject)
                        or subject['source_commit']!=task.input_contract['base_ref']
                        or subject['card_digest']!=digest(qualification['card'])
                        or subject['artifact_bundle_digest']!=digest(qualification['artifact_bundle'])
                        or require_independence(db,route).receipt_digest!=governed['receipt_digest']
                        or not alpha_strategy_reviews_approved(db,route,subject_digest=digest(subject),
                            producer_agent_id=UUID(subject['qualifier_identity']['agent_id']),
                            excluded_agent_ids=[UUID(item) for item in subject['producer_agent_ids']],
                            excluded_identities=subject['producer_identities'],qualifier_identity=subject['qualifier_identity'])):
                    raise ValueError('Current independently reviewed smoke authority required')
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(409, 'Execution preparation authority is no longer current.') from exc
        return
    if (task.task_type == 'engineering_mission'
            and (task.approval_policy or {}).get('kind') == 'accepted_method_engineering'):
        from uuid import UUID
        from fastapi import HTTPException
        from app.contracts.engineering_evidence import decode_engineering_evidence
        try:
            parent = db.get(Task, UUID(task.approval_policy['method_task_id']))
            if parent is None or parent.task_type != 'alpha_method_design':
                raise ValueError('missing method parent')
            require_current_method_authority(db, parent)
            packet = verified_method_result(parent)['review_packet']
            handoff = decode_engineering_evidence(task.input_contract['evidence_context'])['accepted_method_handoff']
            if handoff['packet'] != packet or task.input_contract['base_ref'] != packet['source_commit']:
                raise ValueError('method handoff changed')
            from app.services.evaluator_routing import task_producer_identity
            from app.services.alpha_method_engineering import verified_plan_evidence
            from app.schemas.alpha_campaign import MethodEngineeringRequest
            campaign = db.scalar(select(AlphaCampaign).where(
                AlphaCampaign.campaign_digest == parent.approval_policy['campaign_digest']))
            identity = task_producer_identity(db, parent)
            if campaign is None or identity is None:
                raise ValueError('method campaign or producer missing')
            route, reviews = route_method_review(db, campaign, parent, packet, identity)
            if (str(route.id) != handoff['registration_receipt']['route_id']
                    or reviews is None or any(review.verdict != 'approve' for review in reviews)):
                raise ValueError('method review no longer current')
            request = MethodEngineeringRequest.model_validate(
                campaign.specification['method_engineering_requests'][parent.input_contract['candidate_id']])
            verified_plan_evidence(db, request, packet, parent)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(409, 'Accepted-method engineering authority is no longer current.') from exc
        return
    if (task.task_type == 'alpha_strategy_review'
            and task.input_contract.get('subject', {}).get('review_scope') in {'method_design', 'method_adjudication'}):
        from uuid import UUID
        from fastapi import HTTPException
        try:
            parent = db.get(Task, UUID(task.input_contract['subject']['producer_task_id']))
            if parent is None or parent.task_type != 'alpha_method_design':
                raise ValueError('missing method parent')
            require_current_method_authority(db, parent)
            packet = verified_method_result(parent)['review_packet']
            if task.input_contract['qualification']['artifact_bundle']['method_review_packet'] != packet:
                raise ValueError('method packet changed')
            if task.input_contract['subject']['review_scope'] == 'method_adjudication':
                campaign = db.scalar(select(AlphaCampaign).where(
                    AlphaCampaign.campaign_digest == parent.approval_policy['campaign_digest']))
                if campaign is None or campaign.specification.get('method_dispute_policy') != 'independent_once':
                    raise ValueError('adjudication not authorized')
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(409, 'Method review authority or packet is no longer current.') from exc
        return
    if task.task_type != 'alpha_method_design':
        return
    from fastapi import HTTPException
    contract = MethodTaskContract.model_validate(task.input_contract)
    mandate = db.get(AlphaResearchMandate, contract.mandate_id)
    now = datetime.now(timezone.utc)
    if (mandate is None or mandate.status != 'active'
            or mandate.mandate_digest != contract.mandate_digest
            or not mandate.valid_from <= now < min(mandate.valid_until, contract.valid_until)
            or mandate.specification['bulletproof_source_commit'] != contract.base_ref):
        raise HTTPException(409, 'Method episode authority expired, revoked or source changed.')
    campaign_digest = (task.approval_policy or {}).get('campaign_digest')
    campaign = db.scalar(select(AlphaCampaign).where(AlphaCampaign.campaign_digest == campaign_digest))
    from app.services.alpha_method_recovery import authorized_successor
    if (campaign is None or campaign.status != 'running'
            or campaign.activated_at is None
            or now >= campaign.activated_at + timedelta(seconds=campaign.budget['max_duration_seconds'])
            or not authorized_successor(db, campaign, task)):
        raise HTTPException(409, 'Method campaign authority is no longer current.')


def materialize_method_task(db, campaign, source, parent, request):
    contract = MethodTaskContract.model_validate(request)
    raw = contract.model_dump(mode='json')
    # Serialize duplicate delivery through the existing campaign ownership lock.
    db.execute(select(AlphaCampaign.id).where(AlphaCampaign.id == campaign.id).with_for_update())
    mandate = db.get(AlphaResearchMandate, contract.mandate_id)
    now = datetime.now(timezone.utc)
    if (campaign.status != 'running' or mandate is None or mandate.status != 'active'
            or not mandate.valid_from <= now < mandate.valid_until
            or not now < contract.valid_until <= mandate.valid_until
            or mandate.mandate_digest != contract.mandate_digest
            or str(contract.mandate_id) != str(campaign.specification.get('research_mandate_id'))
            or contract.mandate_digest != campaign.specification.get('research_mandate_digest')
            or contract.base_ref != campaign.specification['bulletproof_source_commit']
            or contract.base_ref != mandate.specification['bulletproof_source_commit']):
        raise ValueError('Current source-bound method authority unavailable')
    candidate_id = str(source.get('discovery_candidate_id', source['source_candidate_id']))
    candidate_digest = source.get('discovery_candidate_digest', source['source_candidate_digest'])
    if (str(contract.candidate_id) != candidate_id or contract.candidate_digest != candidate_digest
            or (campaign.specification.get('method_design_requests') or {}).get(candidate_id) != raw
            or parent.status != 'succeeded'):
        raise ValueError('Method candidate or approved request differs')
    # Until controlled commissioning qualifies automatic selection, only an
    # explicit founder activation of this exact campaign may select this path.
    activation = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'campaign_activated',
        AlphaCampaignEvent.actor == 'founder-operator',
    ))
    if activation is None or activation.payload.get('campaign_digest') != campaign.campaign_digest:
        raise ValueError('Method commissioning requires exact campaign activation')
    number = 'AM-' + digest({'campaign': str(campaign.id), 'parent': str(parent.id), 'contract': raw})[:40]
    existing = db.scalar(select(Task).where(Task.task_number == number))
    if existing is not None:
        if (existing.input_contract != raw or existing.parent_task_id != parent.id
                or existing.task_type != 'alpha_method_design'):
            raise ValueError('Method task immutable identity conflict')
        return existing
    if (candidate_id in (campaign.specification.get('method_engineering_requests') or {})
            or candidate_id in (campaign.specification.get('method_execution_preparation_requests') or {})):
        from app.services.alpha_data_prerequisites import require_data_prerequisites
        from app.services.alpha_campaign import _source_bindings
        require_data_prerequisites(db, {
            'source_commit': contract.base_ref, 'dependencies': contract.dependencies,
            'evidence': contract.evidence_catalog,
        }, contract.candidate_digest, _source_bindings(campaign, source))
    task = build_task(TaskCreate(task_number=number, project='bulletproof_bt',
        task_type='alpha_method_design', title='Diagnose and repair a bounded scientific method',
        objective='Retain scientific identity and support minima; publish evidence for independent review, never approval.',
        parent_task_id=parent.id, created_by='alpha-campaign-director', risk_level=0,
        max_attempts=2, input_contract=raw, required_capabilities=['alpha-method-design'],
        allowed_machines=['vm1-developer'],
        expected_outputs=['method episode state', 'native diagnostic receipts', 'exact review packet or explicit deferral'],
        acceptance_criteria=['Source and mandate bound', 'No self approval', 'Immutable repair budgets'],
        approval_policy={'kind': 'bounded_method_design', 'campaign_digest': campaign.campaign_digest,
                         'mandate_digest': contract.mandate_digest}))
    persist_new_task(db, task)
    return task


def verified_method_result(task):
    """Validate readiness custody, not the method's scientific correctness."""
    contract = MethodTaskContract.model_validate(task.input_contract)
    result = (task.result or {}).get('summary', {}).get('method_episode', {})
    from app.contracts.method_result_transport import decode
    result = decode(result)
    if (task.status != 'succeeded' or result.get('schema_version') not in {'method-task-result-v1', 'method-task-result-v2'}
            or result.get('contract_digest') != digest(contract.model_dump(mode='json'))
            or result.get('result_digest') != digest({k: v for k, v in result.items() if k != 'result_digest'})
            or result.get('scientific_approval') is not False or result.get('execution_authority') is not False):
        raise ValueError('Method result custody mismatch')
    if result['schema_version'] == 'method-task-result-v2':
        from copy import deepcopy
        import json
        result = deepcopy(result)
        # Transport and individual documents stay bounded. Expanded history
        # repeats the same immutable catalog once per authorized tool call.
        audit_limit = 524288 * (1 + contract.policy.max_tool_calls)
        if len(json.dumps(result['state'], sort_keys=True, separators=(',', ':')).encode()) > 524288:
            raise ValueError('Compact method state exceeds bound')
        evidence = result['state']['evidence']
        if 'review_proposal_digest' in result:
            packet = result.get('review_packet')
            if (not isinstance(packet, dict) or 'proposal' in packet
                    or 'review_evidence_refs' not in result
                    or digest(result['state'].get('proposal')) != result['review_proposal_digest']):
                raise ValueError('Invalid method review proposal reference')
            packet['proposal'] = deepcopy(result['state']['proposal'])
        if 'review_evidence_refs' in result:
            refs = result['review_evidence_refs']
            packet = result.get('review_packet')
            if (not isinstance(refs, list) or not 1 <= len(refs) <= 256
                    or any(not isinstance(ref, str) or ref not in evidence for ref in refs)
                    or len(set(refs)) != len(refs)
                    or not isinstance(packet, dict) or 'evidence' in packet):
                raise ValueError('Invalid method review evidence references')
            packet['evidence'] = {ref: evidence[ref] for ref in refs}
            if digest(packet) != result.get('review_packet_digest'):
                raise ValueError('Method review packet digest mismatch')
        envelopes = result.get('state_evidence_envelopes', {})
        if (not isinstance(envelopes, dict)
                or not 1 <= len(envelopes) <= contract.policy.max_tool_calls):
            raise ValueError('Invalid method evidence envelope table')
        leaves = dict(evidence)
        for key, envelope in envelopes.items():
            if (key in leaves or not isinstance(envelope, dict)
                    or set(envelope) != {'disposition', 'evidence', 'findings', 'work_units'}
                    or not isinstance(envelope['evidence'], list)
                    or len(envelope['evidence']) > 256
                    or any(not isinstance(ref, str) or ref not in leaves for ref in envelope['evidence'])
                    or len(set(envelope['evidence'])) != len(envelope['evidence'])):
                raise ValueError('Invalid method evidence envelope references')
            restored = envelope | {'evidence': {ref: leaves[ref] for ref in envelope['evidence']}}
            if len(json.dumps(restored, sort_keys=True, separators=(',', ':')).encode()) > 524288:
                raise ValueError('Reconstructed method diagnostic envelope exceeds bound')
            if digest(restored) != key:
                raise ValueError('Method evidence envelope digest mismatch')
            evidence[key] = restored
            if len(json.dumps(result['state'], sort_keys=True, separators=(',', ':')).encode()) > audit_limit:
                raise ValueError('Reconstructed method state exceeds bound')
        if digest(result['state']) != result.get('audit_state_digest'):
            raise ValueError('Method audit state digest mismatch')
    state = result.get('state', {})
    expected_binding = dict(task_id=str(task.id), source_commit=contract.base_ref,
        mandate_digest=contract.mandate_digest, findings_digest=contract.findings_digest,
        contract_digest=result['contract_digest'], kind='method-episode-v1',
        initial_digest=digest(contract.proposal), policy=contract.policy.model_dump())
    if contract.policy.investigation_tools:
        from app.contracts.recovery_investigation import catalog
        expected_binding['investigation_catalog'] = catalog(contract.policy.investigation_tools)
    if (state.get('binding') != expected_binding
            or state.get('scientific_approval') is not False or state.get('execution_authority') is not False):
        raise ValueError('Method state binding mismatch')
    escalation = state.get('escalation')
    if escalation is not None:
        retained = state.get('evidence', {})
        if (not contract.policy.investigation_tools or not isinstance(escalation, dict)
                or set(escalation) != {'action', 'disposition', 'owner', 'recovery_condition', 'evidence_refs', 'rationale'}
                or escalation.get('action') != 'escalate'
                or escalation.get('disposition') not in {'await_data', 'scientifically_infeasible',
                    'requirements_conflict', 'requires_new_question', 'await_authority_or_capacity', 'infrastructure_repair'}
                or state.get('status') != 'deferred' or state.get('reason') != escalation.get('disposition')
                or any(not isinstance(escalation.get(k), str) or not 1 <= len(escalation[k]) <= limit
                    for k, limit in [('owner', 200), ('recovery_condition', 4000), ('rationale', 4000)])
                or not isinstance(escalation.get('evidence_refs'), list)
                or not 1 <= len(escalation['evidence_refs']) <= 32
                or any(not isinstance(ref, str) or ref not in retained for ref in escalation['evidence_refs'])
                or any(digest(v) != k for k, v in retained.items())):
            raise ValueError('Invalid evidence-bound recovery escalation')
    proposal = state.get('proposal', {})
    if (proposal.get('scientific_identity') != contract.proposal['scientific_identity']
            or proposal.get('support_minima') != contract.proposal['support_minima']):
        raise ValueError('Method result changed frozen scientific identity')
    allowed = set(contract.policy.allowed_method_fields)
    initial_method = contract.proposal['method']
    if initial_method.get('schema_version') == 'design-adequacy-contract-v2':
        old = initial_method['assurance']
        new = proposal.get('method', {}).get('assurance')
        if (not isinstance(new, dict) or new.get('required_outputs') != old['required_outputs']
                or not isinstance(new.get('workload'), dict)
                or digest(new['workload'].get('caps')) != digest(old['workload']['caps'])
                or not isinstance(proposal['method'].get('calibration'), dict)
                or type(proposal['method']['calibration'].get('max_work_units')) is not int
                or proposal['method']['calibration'].get('max_work_units') != initial_method['calibration']['max_work_units']):
            raise ValueError('Method result changed frozen assurance outputs or resource caps')
    if ({k: v for k, v in proposal.get('method', {}).items() if k not in allowed}
            != {k: v for k, v in contract.proposal['method'].items() if k not in allowed}):
        raise ValueError('Method result changed fields outside repair scope')
    for key, limit in (('model_calls', contract.policy.max_model_calls),
                       ('repairs', contract.policy.max_repairs),
                       ('tool_calls', contract.policy.max_tool_calls),
                       ('reserved_work', contract.policy.max_work_units)):
        if type(state.get(key)) is not int or not 0 <= state[key] <= limit:
            raise ValueError('Method result exceeds frozen budgets')
    if state.get('status') == 'ready_for_independent_review':
        packet = result.get('review_packet', {})
        retained = state.get('evidence', {})
        review_evidence = {k: v for k, v in retained.items()
            if not (set(v) == {'disposition', 'evidence', 'findings', 'work_units'}
                and isinstance(v['evidence'], dict)
                and all(retained.get(ref) == doc for ref, doc in v['evidence'].items()))}
        if (packet.get('method_episode_digest') != digest(state)
                or packet.get('source_commit') != contract.base_ref
                or packet.get('proposal') != state.get('proposal')
                or packet.get('requirements') != contract.requirements
                or packet.get('dependencies') != contract.dependencies
                or packet.get('evidence') not in (retained, review_evidence)
                or any(digest(v) != k for k, v in retained.items())
                or not packet.get('evidence')
                or any(digest(v) != k for k, v in packet['evidence'].items())):
            raise ValueError('Method review packet differs from retained state')
        from app.services.native_diagnostics import verify_diagnostic
        request = dict(schema_version='native-diagnostic-request-v1', tool=contract.diagnostic,
                       source_commit=contract.base_ref, subject_digest=digest(proposal), payload=proposal['method'])
        from app.contracts.diagnostic_evidence import referenced_catalog
        catalogs = {digest(contract.evidence_catalog): contract.evidence_catalog}
        projected = referenced_catalog(proposal['method'], contract.evidence_catalog, digest)
        catalogs[digest(projected)] = projected
        receipts = [v for v in packet['evidence'].values()
                    if v.get('schema_version') == 'native-diagnostic-receipt-v1'
                    and v.get('subject_digest') == digest(proposal)
                    and v.get('source_commit') == contract.base_ref
                    and v.get('request_digest') == digest(request)
                    and v.get('evidence_catalog_digest') in catalogs]
        if len(receipts) != 1:
            raise ValueError('Ready method requires exact current native diagnosis')
        verify_diagnostic(receipts[0], request, catalogs[receipts[0]['evidence_catalog_digest']], contract.base_ref, digest(proposal))
        assessment = receipts[0]['result']
        if 'experiment' in proposal['method']:
            consistency = assessment.get('consistency', {})
            if (consistency.get('status') != 'structurally_consistent'
                    or consistency.get('finding_count') != 0 or consistency.get('findings') != []):
                raise ValueError('Structured method lacks native consistency readiness')
        if (assessment.get('status') != 'requires_independent_review_and_native_calibration'
                or assessment.get('contract_digest') != digest(proposal['method'])):
            raise ValueError('Native diagnosis does not establish exact design readiness')
    return result


def advance_method_task(db, campaign, source, parent, request):
    from app.services.alpha_campaign import _append_event
    from app.services.alpha_requirements_handoff import RequirementsPending
    from app.services.evaluator_routing import task_producer_identity

    task = materialize_method_task(db, campaign, source, parent, request)
    from app.services.alpha_method_recovery import recorded_successor, materialize_correction, RecoveryDeferred
    for _ in range(5):
        successor = recorded_successor(db, campaign, task)
        if successor is None:
            break
        task = successor
    else:
        raise ValueError('Method correction lineage exceeds bounded repairs')
    campaign.phase = 'method_design'
    campaign.next_action = 'await_bounded_method_design'
    if task.status in {'queued', 'leased', 'running', 'pending_approval'}:
        return task
    if task.status != 'succeeded':
        return task  # Existing campaign task-failure handling retains the cause.
    result = verified_method_result(task)
    state = result['state']
    if state['status'] != 'ready_for_independent_review':
        from app.contracts.native_design_shape import defects
        if (state['status'] == 'blocked' and state.get('reason') == 'invalid_stage_result'
                and defects(state['proposal']['method'])):
            try:
                correction = materialize_correction(db, campaign, task, result, [], diagnostic_recovery=True)
            except RecoveryDeferred:
                pass  # Preserve the original result and explicit deferral below.
            else:
                campaign.next_action = 'await_bounded_native_shape_correction'
                return correction
        campaign.status = 'needs_attention'
        campaign.next_action = 'method_design_deferred'
        campaign.terminal_reason = {'category': 'method_design_deferred',
            'detail': {'task_id': str(task.id), 'reason': state.get('reason'),
                       'result_digest': result['result_digest']}}
        if state.get('escalation'):
            campaign.terminal_reason['detail']['escalation'] = state['escalation']
        raise RequirementsPending()
    identity = task_producer_identity(db, task)
    if identity is None:
        campaign.next_action = 'restore_method_producer_identity'
        return None
    packet = result['review_packet']
    payload = {'task_id': str(task.id), 'plan_digest': task.plan_digest,
               'producer_identity': identity, 'packet_digest': digest(packet),
               'packet': packet, 'result_digest': result['result_digest'],
               'execution_authority': False, 'scientific_approval': False}
    previous = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'method_packet_published',
        AlphaCampaignEvent.payload['task_id'].astext == str(task.id)))
    if previous is None:
        _append_event(db, campaign, 'method_packet_published', 'alpha-campaign-director', payload)
    elif previous.payload != payload:
        raise ValueError('Published method packet changed')
    campaign.phase = 'independent_method_review'
    campaign.next_action = 'await_independent_method_review'
    engineering_request = (campaign.specification.get('method_engineering_requests') or {}).get(
        str(task.input_contract['candidate_id']))
    preparation_request = (campaign.specification.get('method_execution_preparation_requests') or {}).get(
        str(task.input_contract['candidate_id']))
    if engineering_request is not None or preparation_request is not None:
        from app.services.alpha_method_engineering import verified_plan_evidence, MethodPlanUnavailable
        from app.services.alpha_data_prerequisites import DataPrerequisiteUnavailable, require_data_prerequisites
        from app.schemas.alpha_campaign import MethodEngineeringRequest
        try:
            if engineering_request is not None:
                verified_plan_evidence(db, MethodEngineeringRequest.model_validate(engineering_request), packet, task)
            else:
                from app.services.alpha_campaign import _source_bindings
                require_data_prerequisites(db, packet, task.input_contract['candidate_digest'],
                                           _source_bindings(campaign, source))
        except DataPrerequisiteUnavailable as exc:
            campaign.status = 'needs_attention'
            campaign.next_action = exc.reason_code
            campaign.terminal_reason = {'category': exc.reason_code, 'detail': {
                'task_id': str(task.id), 'packet_digest': digest(packet), **exc.detail}}
            raise RequirementsPending() from exc
        except MethodPlanUnavailable as exc:
            campaign.status = 'needs_attention'
            campaign.next_action = 'method_dependency_deferred'
            campaign.terminal_reason = {'category': 'method_dependency_deferred', 'detail': {
                'task_id': str(task.id), 'reason': str(exc),
                'owner': 'native_feasibility_planner',
                'feasibility_task_id': engineering_request['feasibility_task_id'],
                'packet_digest': digest(packet), 'execution_authority': False}}
            raise RequirementsPending() from exc
    route, reviews = route_method_review(db, campaign, task, packet, identity)
    if reviews is not None:
        campaign.next_action = ('materialize_accepted_method_handoff'
                                if all(review.verdict == 'approve' for review in reviews)
                                else 'adjudicate_method_review_findings')
        if any(review.verdict != 'approve' for review in reviews):
            from app.services.alpha_method_adjudication import adjudicate_method
            try:
                from datetime import datetime, timezone
                from app.services.alpha_method_recovery import require_recovery_capacity
                require_recovery_capacity(task, result, now=datetime.now(timezone.utc))
                adjudication = adjudicate_method(db, campaign, task, packet, identity, route, reviews)
                if adjudication is not None and adjudication.get('pending'):
                    return None
                correction = materialize_correction(db, campaign, task, result, reviews,
                                                   adjudication=adjudication)
            except RecoveryDeferred as exc:
                campaign.status = 'needs_attention'
                campaign.next_action = 'method_design_deferred'
                campaign.terminal_reason = {'category': 'method_design_deferred',
                    'detail': {'task_id': str(task.id), 'reason': str(exc),
                               'route_id': str(route.id), 'result_digest': result['result_digest']}}
                raise RequirementsPending()
            campaign.phase = 'method_design'
            campaign.next_action = 'await_bounded_method_correction'
            return correction
        preparation_request = (campaign.specification.get('method_execution_preparation_requests') or {}).get(
            str(task.input_contract['candidate_id']))
        if preparation_request is not None:
            from app.services.alpha_execution_preparation import materialize_execution_preparation
            preparation = materialize_execution_preparation(
                db, campaign, source, task, packet, identity, route, preparation_request)
            campaign.phase = 'execution_preparation'
            campaign.next_action = {
                'pending_approval': 'approve_execution_preparation',
                'succeeded': 'approve_prepared_execution_card',
                'failed': 'execution_preparation_failed',
                'cancelled': 'execution_preparation_cancelled',
            }.get(preparation.status, 'await_execution_preparation')
            if preparation.status == 'succeeded':
                from app.services.alpha_execution_preparation import publish_execution_preparation, advance_prepared_card
                prepared = publish_execution_preparation(db, campaign, preparation, preparation_request['released_template'])
                compiled = advance_prepared_card(db, campaign, task, preparation, prepared)
                if compiled.status == 'succeeded':
                    from app.services.alpha_execution_preparation import route_execution_review, materialize_reviewed_smoke
                    reviewed=route_execution_review(db,campaign,task,preparation,compiled,prepared,preparation_request)
                    if reviewed is not None:
                        smoke=materialize_reviewed_smoke(db,campaign,compiled,reviewed,preparation_request)
                        if smoke is not None:
                            if smoke.status=='succeeded':
                                from app.services.alpha_execution_preparation import consume_reviewed_smoke
                                consume_reviewed_smoke(db,campaign,smoke)
                            return smoke
                return compiled
            return preparation
        if all(review.verdict == 'approve' for review in reviews) and engineering_request is not None:
            from app.services.alpha_method_engineering import materialize_method_engineering
            engineering = materialize_method_engineering(
                db, campaign, task, packet, identity, route, engineering_request)
            campaign.phase = 'strategy_engineering'
            campaign.next_action = {
                'pending_approval': 'founder_strategy_engineering_approval',
                'succeeded': 'founder_merge_strategy_and_rebind_source_commit',
                'failed': 'strategy_engineering_failed',
                'cancelled': 'strategy_engineering_cancelled',
            }.get(engineering.status, 'await_bounded_strategy_engineering')
            if engineering.status in {'succeeded', 'failed', 'cancelled'}:
                campaign.status = 'needs_attention'
                campaign.terminal_reason = {'category': campaign.next_action, 'task_id': str(engineering.id)}
            return engineering
    elif route.status == 'blocked':
        campaign.next_action = 'restore_independent_method_review_routing'
    # Accepted review still needs native-plan custody before engineering.
    return None


def method_review_qualification(packet):
    import json
    qualification = {'card': packet['proposal'],
                     'artifact_bundle': {'method_review_packet': packet}}
    if len(json.dumps(qualification, sort_keys=True, separators=(',', ':')).encode()) > 250000:
        qualification['card'] = {
            'schema_version': 'method-review-proposal-reference-v1',
            'proposal_digest': digest(packet['proposal']),
            'proposal_location': 'qualification.artifact_bundle.method_review_packet.proposal',
            'scientific_approval': False, 'execution_authority': False,
        }
    return qualification


def route_method_review(db, campaign, task, packet, identity):
    """Publish a separate review route without converting readiness to authority."""
    from app.models.evaluator_routing import EvaluationRoute
    from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity, MethodStrategyReview
    from app.schemas.method_verdict import validate_method_review
    from app.services.evaluator_routing import create_route, validated_alpha_strategy_reviews
    from app.services.alpha_campaign import _append_event, _materialize_strategy_review_tasks

    require_current_method_authority(db, task)
    qualification = method_review_qualification(packet)
    excluded = []
    handoff_request = (campaign.specification.get('method_engineering_requests') or {}).get(
        str(task.input_contract['candidate_id']))
    if handoff_request is not None:
        from uuid import UUID
        from app.services.evaluator_routing import task_producer_identity
        planning = db.get(Task, UUID(handoff_request['feasibility_task_id']))
        native_identity = task_producer_identity(db, planning) if planning is not None else None
        if native_identity is None:
            raise ValueError('Native planning producer custody missing')
        if native_identity != identity:
            excluded.append(native_identity)
    subject = {'review_scope': 'method_design', 'source_commit': packet['source_commit'],
               'card_digest': digest(qualification['card']),
               'artifact_bundle_digest': digest(qualification['artifact_bundle']),
               'packet_digest': digest(packet), 'producer_task_id': str(task.id),
               'producer_agent_ids': sorted({str(identity['agent_id']),
                                            *(str(item['agent_id']) for item in excluded)})}
    previous = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'method_review_routed',
        AlphaCampaignEvent.payload['subject_digest'].astext == digest(subject)))
    if previous is None:
        route = create_route(db, EvaluationRouteCreate(
            subject_type='alpha_strategy_qualification', subject_id=f'method:{task.id}',
            subject_digest=digest(subject),
            producer=ProducerIdentity.model_validate(identity | {'actor': str(identity['agent_id'])}),
            excluded_producers=[ProducerIdentity.model_validate(item | {'actor': str(item['agent_id'])})
                                for item in excluded],
            required_review_kinds=['strategy_spec', 'causality_leakage'],
            requested_by='alpha-campaign-director'))
        _append_event(db, campaign, 'method_review_routed', 'alpha-campaign-director',
                      {'subject_digest': digest(subject), 'subject': subject,
                       'qualification': qualification, 'route_id': str(route.id)})
    else:
        if previous.payload['qualification'] != qualification or previous.payload['subject'] != subject:
            raise ValueError('Method review publication changed')
        route = db.get(EvaluationRoute, previous.payload['route_id'])
        if route is None:
            raise ValueError('Method review route missing')
    _materialize_strategy_review_tasks(db, route, subject, qualification)
    reviews = validated_alpha_strategy_reviews(db, route, subject_digest=digest(subject),
        producer_agent_id=identity['agent_id'],
        excluded_agent_ids=[item['agent_id'] for item in excluded], excluded_identities=excluded)
    if reviews is None:
        return route, None
    current_review_identities(db, route, expected_count=2)
    for review in reviews:
        if not isinstance(review, MethodStrategyReview):
            raise ValueError('Legacy strategy approval is not method evidence')
        validate_method_review(review, packet, digest)
    return route, reviews


def current_review_identities(db, route, *, expected_count):
    from app.models.evaluator_routing import EvaluatorAssignment, EvaluatorProfile
    from app.models.agent import Agent
    from app.services.evaluator_routing import producer_identity_for_lease, _profile_identity
    assignments = db.scalars(select(EvaluatorAssignment).where(
        EvaluatorAssignment.route_id == route.id)).all()
    if len(assignments) != expected_count:
        raise ValueError('Method review assignment count differs')
    identities = []
    for assignment in assignments:
        profile = db.get(EvaluatorProfile, assignment.evaluator_profile_id)
        agent = db.get(Agent, profile.agent_id) if profile is not None else None
        from app.models import PackageDeployment, RolePackage
        deployed = db.scalar(select(RolePackage.manifest_digest).join(
            PackageDeployment, PackageDeployment.package_id == RolePackage.id).where(
                PackageDeployment.agent_id == profile.agent_id,
                PackageDeployment.package_id == profile.package_id,
                PackageDeployment.is_active.is_(True))) if profile is not None else None
        if (profile is None or profile.status != 'active' or agent is None or not agent.is_enabled
                or deployed != profile.package_digest
                or producer_identity_for_lease(db, agent, [profile.package_digest]) != _profile_identity(profile)):
            raise ValueError('Method reviewer registration is no longer current')
        identities.append(_profile_identity(profile))
    return identities
