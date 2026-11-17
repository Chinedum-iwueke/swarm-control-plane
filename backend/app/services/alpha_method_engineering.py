"""Source-bound engineering publication from independently accepted methods."""
from copy import deepcopy

from sqlalchemy import select

from app.contracts.engineering_evidence import decode_engineering_evidence, encode_engineering_evidence
from app.models.task import Task
from app.schemas.alpha_campaign import MethodEngineeringRequest
from app.schemas.task import TaskCreate
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


def verified_plan_evidence(db, request, packet, method_task):
    from app.services.alpha_requirements_feasibility import verified_report
    from app.models.alpha_discovery import AlphaDiscoveryCandidate

    planning = db.get(Task, request.feasibility_task_id)
    if (planning is None or planning.status != 'succeeded'
            or planning.task_type != 'alpha_data_admission'
            or planning.input_contract.get('base_ref') != packet['source_commit']):
        raise ValueError('Current successful native planning task required')
    evidence = planning.input_contract.get('feasibility_evidence')
    if not isinstance(evidence, dict):
        raise ValueError('Native planning inputs missing')
    candidate = db.get(AlphaDiscoveryCandidate, method_task.input_contract['candidate_id'])
    if (candidate is None or candidate.candidate_digest != method_task.input_contract['candidate_digest']
            or evidence.get('discovery_candidate') != candidate.document):
        raise ValueError('Native plans belong to another candidate')
    report = verified_report(planning, evidence, packet['source_commit'])
    if (report['status'] != 'ready' or digest(report) != request.plan_evidence_digest
            or packet['evidence'].get(request.plan_evidence_digest) != report):
        raise ValueError('Reviewed evidence does not contain the exact ready native plans')
    for mode, plan in report['validation_plans'].items():
        if (plan.get('schema_version') != 'requirements-aware-validation-plan-v1'
                or plan.get('status') != 'ready' or plan.get('reasons')
                or not plan.get('partitions') or plan.get('mode') != mode):
            raise ValueError('Native plans are not ready for both validation modes')
    template_evidence = decode_engineering_evidence(request.contract.evidence_context)
    for key in ('discovery_candidate', 'dataset_bindings', 'representation_plan', 'window'):
        if key not in evidence or template_evidence.get(key) != evidence[key]:
            raise ValueError('Engineering template differs from native planning inputs: ' + key)
    return report


def bound_engineering_contract(template, *, packet, reviews, identities, producers,
                               registration_receipt, plan_evidence_digest):
    """Caller must first verify registered review and native plan custody."""
    raw = template.model_dump(mode='json')
    evidence = decode_engineering_evidence(raw['evidence_context'])
    if 'accepted_method_handoff' in evidence:
        raise ValueError('Cannot rebind an existing accepted-method handoff')
    raw['evidence_context'] = encode_engineering_evidence(evidence)
    state = dict(status='review_complete', packet=deepcopy(packet), reviews=deepcopy(reviews),
                 binding={'reviewers': identities, 'producers': producers}, execution_authority=False)
    handoff = dict(schema_version='accepted-method-engineering-handoff-v1',
        review_state_digest=digest(state), packet=deepcopy(packet), reviews=deepcopy(reviews),
        registration_receipt=deepcopy(registration_receipt), review_identity_bindings=state['binding'],
        plan_evidence_digest=plan_evidence_digest, contract_basis_digest=digest(raw),
        execution_authority=False)
    handoff['handoff_digest'] = digest(handoff)
    evidence['accepted_method_handoff'] = handoff
    raw['evidence_context'] = encode_engineering_evidence(evidence)
    return type(template).model_validate(raw)


def materialize_method_engineering(db, campaign, method_task, packet, identity, route, request):
    from app.services.alpha_method_tasks import require_current_method_authority, route_method_review
    from app.services.evaluator_routing import require_independence, _profile_identity
    from app.models.evaluator_routing import EvaluatorAssignment, EvaluatorProfile, EvaluationRouteEvent
    from app.services.alpha_campaign import STRATEGY_ENGINEERING_ALLOWED_PATHS

    require_current_method_authority(db, method_task)
    request = MethodEngineeringRequest.model_validate(request)
    if (campaign.specification.get('method_engineering_requests') or {}).get(
            str(method_task.input_contract['candidate_id'])) != request.model_dump(mode='json'):
        raise ValueError('Engineering request differs from frozen campaign authority')
    if (request.contract.base_ref != packet['source_commit']
            or not set(request.contract.allowed_paths) <= set(STRATEGY_ENGINEERING_ALLOWED_PATHS)):
        raise ValueError('Engineering source or scope exceeds approved native strategy boundary')
    verified_plan_evidence(db, request, packet, method_task)
    current_route, accepted = route_method_review(db, campaign, method_task, packet, identity)
    if current_route.id != route.id or accepted is None or any(r.verdict != 'approve' for r in accepted):
        raise ValueError('Current independent method acceptance required')
    receipt = require_independence(db, route)
    assignments = db.scalars(select(EvaluatorAssignment).where(EvaluatorAssignment.route_id == route.id)).all()
    events = db.scalars(select(EvaluationRouteEvent).where(EvaluationRouteEvent.route_id == route.id)).all()
    reviews, identities = {}, {}
    for assignment in assignments:
        profile = db.get(EvaluatorProfile, assignment.evaluator_profile_id)
        recorded = [event.payload['alpha_strategy_review'] for event in events
                    if event.payload.get('assignment_digest') == assignment.assignment_digest
                    and event.payload.get('review_digest') == assignment.review_digest
                    and 'alpha_strategy_review' in event.payload]
        if len(recorded) != 1:
            raise ValueError('Exact method review event missing')
        actor = _profile_identity(profile)
        compact = {key: actor[key] for key in ('agent_id', 'profile_digest', 'context_group')}
        identities[assignment.review_kind] = compact
        reviews[assignment.review_kind] = {'identity': compact, 'verdict': recorded[0]['method_verdict']}
    producers = [{key: identity[key] for key in ('agent_id', 'profile_digest', 'context_group')}]
    from app.services.evaluator_routing import task_producer_identity
    native_identity = task_producer_identity(db, db.get(Task, request.feasibility_task_id))
    if native_identity is None:
        raise ValueError('Native plan producer identity missing')
    native_compact = {key: native_identity[key] for key in ('agent_id', 'profile_digest', 'context_group')}
    if native_compact not in producers:
        producers.append(native_compact)
    contract = bound_engineering_contract(request.contract, packet=packet, reviews=reviews,
        identities=identities, producers=producers,
        registration_receipt={'route_id': str(route.id), 'receipt_digest': receipt.receipt_digest},
        plan_evidence_digest=request.plan_evidence_digest).model_dump(mode='json')
    number = 'AME-' + digest({'campaign': str(campaign.id), 'method_task': str(method_task.id),
                             'contract': contract})[:40]
    existing = db.scalar(select(Task).where(Task.task_number == number))
    if existing is not None:
        if existing.input_contract != contract or existing.parent_task_id != method_task.id:
            raise ValueError('Accepted-method engineering identity conflict')
        return existing
    task = build_task(TaskCreate(task_number=number, project='bulletproof_bt',
        task_type='engineering_mission', title='Engineer independently accepted method',
        objective=contract['objective'], parent_task_id=method_task.id, created_by='alpha-campaign-director',
        risk_level=1, max_attempts=2, approval_required=True, input_contract=contract,
        required_capabilities=['alpha-strategy-engineering', 'git', 'python', 'testing'],
        allowed_machines=['vm1-developer'], expected_outputs=['patch', 'validation', 'review', 'pr_bundle'],
        acceptance_criteria=contract['acceptance_criteria'],
        approval_policy={'kind': 'accepted_method_engineering', 'campaign_digest': campaign.campaign_digest,
                         'method_task_id': str(method_task.id), 'method_packet_digest': digest(packet)}))
    persist_new_task(db, task)
    return task
