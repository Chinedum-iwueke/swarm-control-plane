"""Immutable accepted requirements; publication never grants execution authority."""
from sqlalchemy import select

from app.contracts.requirements_repair import diagnostic_payload
from app.models.alpha_campaign import AlphaCampaignEvent
from app.services.graph import digest_document as digest


def publish_requirements_handoff(db, campaign, task):
    from app.services.alpha_campaign import _append_event
    from app.services.alpha_method_tasks import verified_method_result, route_method_review
    from app.services.evaluator_routing import task_producer_identity

    contract = task.input_contract
    if contract.get('diagnostic') != 'requirements_feasibility_v1':
        raise ValueError('Requirements handoff requires native requirements diagnosis')
    if (task.status != 'succeeded'
            or contract['base_ref'] != campaign.specification['bulletproof_source_commit']
            or (task.approval_policy or {}).get('campaign_digest') != campaign.campaign_digest):
        raise ValueError('Requirements handoff campaign/source binding mismatch')
    result = verified_method_result(task)
    if result['state']['status'] != 'ready_for_independent_review':
        raise ValueError('Deferred method cannot publish an accepted handoff')
    packet = result['review_packet']
    identity = task_producer_identity(db, task)
    if identity is None:
        raise ValueError('Requirements handoff lacks producer custody')
    route, reviews = route_method_review(db, campaign, task, packet, identity)
    if reviews is None or len(reviews) != 2 or any(r.verdict != 'approve' for r in reviews):
        raise ValueError('Requirements handoff requires both independent approvals')
    inputs, lineage = diagnostic_payload(packet['proposal'], contract['evidence_catalog'],
        contract['dependencies'], contract['base_ref'], digest)
    if lineage is None:
        raise ValueError('Requirements handoff requires explicit coverage-clock lineage')
    receipts = [value for value in packet['evidence'].values()
                if value.get('schema_version') == 'native-diagnostic-receipt-v1'
                and value.get('subject_digest') == digest(packet['proposal'])
                and value.get('result', {}).get('input_digest') == digest(inputs)]
    if len(receipts) != 1:
        raise ValueError('Requirements handoff lacks unique current native receipt')
    payload = {
        'schema_version': 'accepted-requirements-handoff-v1',
        'method_task_id': str(task.id), 'plan_digest': task.plan_digest,
        'campaign_digest': campaign.campaign_digest, 'source_commit': contract['base_ref'],
        'parent_candidate_id': contract['candidate_id'],
        'parent_candidate_digest': contract['candidate_digest'],
        'result_digest': result['result_digest'], 'packet_digest': digest(packet),
        'inputs': inputs, 'lineage': lineage,
        'native_receipt_digest': digest(receipts[0]),
        'native_report_digest': receipts[0]['result']['report_digest'],
        'review_route_id': str(route.id), 'review_subject_digest': route.subject_digest,
        'review_digests': sorted(digest(r.model_dump(mode='json')) for r in reviews),
        'method_review_accepted': True, 'scientific_certification': False,
        'engineering_authority': False, 'execution_authority': False,
        'requires_separate_downstream_authority': True,
    }
    existing = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'accepted_requirements_handoff_published',
        AlphaCampaignEvent.payload['method_task_id'].astext == str(task.id)))
    if existing is not None:
        if existing.payload != payload:
            raise ValueError('Accepted requirements handoff changed')
        return existing
    # Reconciliation holds the campaign lock; repeat publication is an exact replay.
    return _append_event(db, campaign, 'accepted_requirements_handoff_published',
                         'alpha-method-director', payload)
