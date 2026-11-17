"""Immutable, budget-conserving successors for independently rejected methods."""
from copy import deepcopy
from datetime import datetime, timezone
import math

from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignEvent
from app.models.task import Task
from app.schemas.method_task import MethodTaskContract
from app.schemas.task import TaskCreate
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


class RecoveryDeferred(ValueError):
    pass


def require_recovery_capacity(parent, result, *, now):
    """Do not pay for adjudication when even an unchanged recheck is impossible."""
    contract = MethodTaskContract.model_validate(parent.input_contract)
    state = result['state']
    deadline = float(state['deadline'])
    if not math.isfinite(deadline) or parent.started_at is None:
        raise ValueError('Observed original execution deadline required')
    deadline = min(deadline, contract.valid_until.timestamp(),
                   parent.started_at.timestamp() + contract.policy.max_duration_seconds)
    if deadline - now.timestamp() < 1:
        raise RecoveryDeferred('deadline_exhausted')
    if (contract.policy.max_tool_calls - state['tool_calls'] < 1
            or contract.policy.max_work_units - state['reserved_work'] < contract.policy.tool_work_limit):
        raise RecoveryDeferred('native_recheck_budget_exhausted')


def correction_contract(parent, result, reviews, *, now, adjudication=None):
    contract = MethodTaskContract.model_validate(parent.input_contract)
    state = result['state']
    if state['status'] != 'ready_for_independent_review' or not reviews or all(r.verdict == 'approve' for r in reviews):
        raise ValueError('Independent rejected method required')
    packet = result['review_packet']
    from app.schemas.method_verdict import validate_method_review
    for review in reviews:
        validate_method_review(review, packet, digest)
    recheck = False
    if adjudication is not None:
        from app.schemas.evaluator_routing import MethodAdjudicationReview
        from app.schemas.method_adjudication import validate_adjudication
        decision = MethodAdjudicationReview.model_validate(adjudication['review'])
        validate_adjudication(decision, {'method_review_packet': packet,
            'rejected_reviews': [r.model_dump(mode='json') for r in reviews if r.verdict == 'reject']}, digest)
        if decision.method_adjudication.decision == 'disputed':
            raise RecoveryDeferred('independent_method_dispute_unresolved')
        recheck = decision.method_adjudication.decision == 'recheck'
    policy = contract.policy.model_dump()
    for name, used in (('max_repairs', 'repairs'), ('max_model_calls', 'model_calls'),
                      ('max_tool_calls', 'tool_calls'), ('max_work_units', 'reserved_work')):
        policy[name] -= state[used]
    # A review-driven successor needs at least one correction and two diagnoses.
    tools_needed = 1 if recheck else 2
    if ((not recheck and (policy['max_repairs'] < 1 or policy['max_model_calls'] < 1))
            or policy['max_tool_calls'] < tools_needed
            or policy['max_work_units'] < tools_needed * policy['tool_work_limit']):
        raise RecoveryDeferred('repair_or_model_budget_exhausted')
    deadline = float(state['deadline'])
    if not math.isfinite(deadline) or parent.started_at is None:
        raise ValueError('Observed original execution deadline required')
    deadline = min(deadline, contract.valid_until.timestamp(),
                   parent.started_at.timestamp() + contract.policy.max_duration_seconds)
    remaining = int(deadline - now.timestamp())
    if remaining < 1:
        raise RecoveryDeferred('deadline_exhausted')
    policy['max_duration_seconds'] = min(policy['max_duration_seconds'], remaining)
    rejected = [review.model_dump(mode='json') for review in reviews if review.verdict == 'reject']
    if sum(len(review['method_verdict']['findings']) for review in rejected) > 32:
        raise RecoveryDeferred('context_requires_compaction')
    report = dict(schema_version='method-review-recheck-v1' if recheck else 'method-review-correction-v1', parent_task_id=str(parent.id),
                  packet_digest=digest(packet), proposal_digest=digest(state['proposal']),
                  reviews=rejected, scientific_approval=False, execution_authority=False)
    catalog = {key: value for key, value in (contract.evidence_catalog | packet['evidence']).items()
               if value.get('schema_version') != 'method-review-correction-v1'}
    if adjudication is not None:
        # The prior packet remains in the adjudication receipt, not as a second
        # current native diagnosis of the same proposal in a recheck packet.
        catalog = {k: v for k, v in catalog.items() if not (
            v.get('schema_version') == 'native-diagnostic-receipt-v1'
            and v.get('subject_digest') == digest(state['proposal']))}
        catalog[digest(adjudication)] = deepcopy(adjudication)
    catalog[digest(report)] = report
    raw = contract.model_dump(mode='json') | dict(
        proposal=deepcopy(state['proposal']), policy=policy, findings_digest=digest(report),
        evidence_catalog=catalog, valid_until=datetime.fromtimestamp(deadline, timezone.utc).isoformat())
    try:
        return MethodTaskContract.model_validate(raw).model_dump(mode='json')
    except ValueError as exc:
        raise RecoveryDeferred('context_requires_compaction') from exc


def recorded_successor(db, campaign, parent):
    event = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == 'method_correction_created',
        AlphaCampaignEvent.payload['parent_task_id'].astext == str(parent.id)))
    if event is None:
        return None
    successor = db.get(Task, event.payload['task_id'])
    if (successor is None or successor.parent_task_id != parent.id
            or successor.task_type != 'alpha_method_design'
            or successor.input_contract != event.payload['contract']
            or digest(successor.input_contract) != event.payload['contract_digest']):
        raise ValueError('Method correction lineage changed')
    return successor


def diagnostic_correction_contract(parent, result, *, now):
    from app.contracts.native_design_shape import defects, SHAPE
    contract = MethodTaskContract.model_validate(parent.input_contract)
    state = result['state']
    invalid = defects(state['proposal']['method'])
    if state['status'] != 'blocked' or state.get('reason') != 'invalid_stage_result' or not invalid:
        raise ValueError('Only a reproducible wire-shape defect permits diagnostic recovery')
    if not set(invalid) <= set(contract.policy.allowed_method_fields):
        raise RecoveryDeferred('shape_defect_outside_approved_repair_scope')
    require_recovery_capacity(parent, result, now=now)
    policy = contract.policy.model_dump()
    for name, used in (('max_repairs', 'repairs'), ('max_model_calls', 'model_calls'),
                      ('max_tool_calls', 'tool_calls'), ('max_work_units', 'reserved_work')):
        policy[name] -= state[used]
    if (policy['max_repairs'] < 1 or policy['max_model_calls'] < 1
            or policy['max_tool_calls'] < 2 or policy['max_work_units'] < 2*policy['tool_work_limit']):
        raise RecoveryDeferred('repair_or_model_budget_exhausted')
    deadline = min(float(state['deadline']), contract.valid_until.timestamp(),
                   parent.started_at.timestamp() + contract.policy.max_duration_seconds)
    policy['max_duration_seconds'] = int(deadline - now.timestamp())
    report = dict(schema_version='method-shape-recovery-v1', parent_task_id=str(parent.id),
                  result_digest=result['result_digest'], defects=invalid, required_shape=SHAPE,
                  scientific_approval=False, execution_authority=False)
    catalog = dict(contract.evidence_catalog)
    catalog[digest(report)] = report
    try:
        return MethodTaskContract.model_validate(contract.model_dump(mode='json') | dict(
            proposal=deepcopy(state['proposal']), policy=policy, evidence_catalog=catalog,
            findings_digest=digest(report), valid_until=datetime.fromtimestamp(deadline, timezone.utc).isoformat()
        )).model_dump(mode='json')
    except ValueError as exc:
        raise RecoveryDeferred('context_requires_compaction') from exc


def materialize_correction(db, campaign, parent, result, reviews, *, adjudication=None,
                           diagnostic_recovery=False):
    from app.services.alpha_campaign import _append_event
    from app.services.alpha_method_tasks import require_current_method_authority
    # Serialize the receipt lookup and task creation even outside reconciliation.
    db.execute(select(AlphaCampaign.id).where(AlphaCampaign.id == campaign.id).with_for_update())
    require_current_method_authority(db, parent)
    existing = recorded_successor(db, campaign, parent)
    if existing is not None:
        return existing
    raw = (diagnostic_correction_contract(parent, result, now=datetime.now(timezone.utc))
           if diagnostic_recovery else correction_contract(parent, result, reviews,
                now=datetime.now(timezone.utc), adjudication=adjudication))
    task = build_task(TaskCreate(
        task_number='AMC-' + digest({'parent': str(parent.id), 'reviews': [r.model_dump(mode='json') for r in reviews]})[:40],
        project='bulletproof_bt', task_type='alpha_method_design',
        title='Correct native method shape' if diagnostic_recovery else 'Correct independently reviewed method findings',
        objective='Repair only approved method fields within remaining original budgets; obtain fresh independent review.',
        parent_task_id=parent.id, created_by='alpha-campaign-director', risk_level=0,
        max_attempts=1, input_contract=raw, required_capabilities=['alpha-method-design'],
        allowed_machines=['vm1-developer'], expected_outputs=['method episode state', 'exact review packet or deferral'],
        acceptance_criteria=['Frozen scientific identity', 'No budget or deadline reset', 'No self approval'],
        approval_policy={'kind': 'bounded_method_correction', 'campaign_digest': campaign.campaign_digest,
                         'mandate_digest': raw['mandate_digest']}))
    persist_new_task(db, task)
    db.flush()
    _append_event(db, campaign, 'method_correction_created', 'alpha-campaign-director',
                  {'parent_task_id': str(parent.id), 'task_id': str(task.id), 'contract': raw,
                   'contract_digest': digest(raw), 'result_digest': result['result_digest'],
                   'reviews_digest': digest([r.model_dump(mode='json') for r in reviews]),
                   'execution_authority': False})
    return task


def authorized_successor(db, campaign, task):
    """Follow only recorded server-created successors back to the frozen request."""
    seen = set()
    while True:
        if task.id in seen or len(seen) > 4:
            return False
        seen.add(task.id)
        expected = (campaign.specification.get('method_design_requests') or {}).get(
            str(task.input_contract.get('candidate_id')))
        if task.input_contract == expected:
            return True
        parent = db.get(Task, task.parent_task_id)
        if parent is None or parent.task_type != 'alpha_method_design':
            return False
        try:
            successor = recorded_successor(db, campaign, parent)
        except (KeyError, TypeError, ValueError):
            return False
        if successor is None or successor.id != task.id:
            return False
        task = parent
