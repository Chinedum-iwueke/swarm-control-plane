"""One independently routed interpretation check per bounded method lineage."""
from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaignEvent
from app.models.evaluator_routing import EvaluationRoute
from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity, MethodAdjudicationReview
from app.schemas.method_adjudication import validate_adjudication
from app.services.graph import digest_document as digest


def adjudicate_method(db, campaign, task, packet, identity, original_route, reviews):
    from app.services.alpha_campaign import _append_event, _materialize_strategy_review_tasks
    from app.services.alpha_method_tasks import require_current_method_authority, current_review_identities
    from app.services.evaluator_routing import create_route, validated_alpha_strategy_reviews

    if campaign.specification.get('method_dispute_policy') != 'independent_once':
        return None
    require_current_method_authority(db, task)
    if any(v.get('schema_version') == 'method-adjudication-receipt-v1'
           for v in task.input_contract['evidence_catalog'].values()):
        return None  # The lineage has already consumed its adjudication allowance.
    excluded = current_review_identities(db, original_route, expected_count=2)
    excluded += original_route.policy.get('excluded_producers', [])
    rejected = [r.model_dump(mode='json') for r in reviews if r.verdict == 'reject']
    bundle = {'method_review_packet': packet, 'rejected_reviews': rejected}
    qualification = {'card': packet['proposal'], 'artifact_bundle': bundle}
    subject = {'review_scope': 'method_adjudication', 'source_commit': packet['source_commit'],
               'producer_task_id': str(task.id), 'packet_digest': digest(packet),
               'card_digest': digest(qualification['card']), 'artifact_bundle_digest': digest(bundle),
               'original_route_id': str(original_route.id),
               'producer_agent_ids': sorted({str(identity['agent_id']), *(str(i['agent_id']) for i in excluded)})}
    previous = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'method_adjudication_routed',
        AlphaCampaignEvent.payload['task_id'].astext == str(task.id)))
    if previous is None:
        route = create_route(db, EvaluationRouteCreate(
            subject_type='alpha_strategy_qualification', subject_id=f'method-dispute:{task.id}',
            subject_digest=digest(subject),
            producer=ProducerIdentity.model_validate(identity | {'actor': str(identity['agent_id'])}),
            excluded_producers=[ProducerIdentity.model_validate(i | {'actor': str(i['agent_id'])}) for i in excluded],
            required_review_kinds=['method_adjudication'], requested_by='alpha-campaign-director'))
        _append_event(db, campaign, 'method_adjudication_routed', 'alpha-campaign-director',
                      {'task_id': str(task.id), 'subject': subject, 'qualification': qualification,
                       'route_id': str(route.id)})
    else:
        if previous.payload['subject'] != subject or previous.payload['qualification'] != qualification:
            raise ValueError('Method adjudication publication changed')
        route = db.get(EvaluationRoute, previous.payload['route_id'])
        if route is None:
            raise ValueError('Method adjudication route missing')
    _materialize_strategy_review_tasks(db, route, subject, qualification)
    decisions = validated_alpha_strategy_reviews(db, route, subject_digest=digest(subject),
        producer_agent_id=identity['agent_id'], excluded_agent_ids=[i['agent_id'] for i in excluded],
        excluded_identities=excluded, required_review_kinds=('method_adjudication',))
    if decisions is None:
        campaign.phase = 'independent_method_review'
        campaign.next_action = ('restore_method_adjudication_routing' if route.status == 'blocked'
                                else 'await_independent_method_adjudication')
        return {'pending': True}
    judges = current_review_identities(db, route, expected_count=1)
    if len(decisions) != 1 or not isinstance(decisions[0], MethodAdjudicationReview):
        raise ValueError('Exact independent adjudication required')
    validate_adjudication(decisions[0], bundle, digest)
    return {'schema_version': 'method-adjudication-receipt-v1', 'route_id': str(route.id),
            'identity': judges[0], 'review': decisions[0].model_dump(mode='json'),
            'prior_packet': packet, 'rejected_reviews': rejected,
            'scientific_approval': False, 'execution_authority': False}
