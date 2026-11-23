"""Prepare a budget-amended proposal for separate exact-digest activation."""
from copy import deepcopy

from app.schemas.method_task import MethodTaskContract, canonical_digest


def bind_prospective_budget(contract, caps):
    """No authorization is granted; callers must register and activate a successor."""
    value = deepcopy(contract)
    parent = canonical_digest(value['proposal'])
    method = value['proposal']['method']
    if method.get('schema_version') != 'design-adequacy-contract-v2':
        raise ValueError('Budget amendment requires V2 dimensioned workload')
    if set(caps) != set(method['assurance']['workload']['caps']):
        raise ValueError('Budget amendment cannot add or remove work units')
    amendment = dict(schema_version='method-budget-amendment-v1',
        parent_proposal_digest=parent, mandate_digest=value['mandate_digest'],
        prior_caps=deepcopy(method['assurance']['workload']['caps']),
        prospective_caps=deepcopy(caps), execution_authority=False)
    method['assurance']['workload']['caps'] = deepcopy(caps)
    method['calibration']['max_work_units'] = caps['statistic_evaluation']
    key = canonical_digest(amendment)
    value['evidence_catalog'][key] = amendment
    value['dependencies']['prospective_budget_amendment'] = key
    consistency = dict(schema_version='method-amendment-consistency-v1',
        amendment_digest=key, proposal_digest=canonical_digest(value['proposal']),
        invalidated_fields=['dependence_assumptions', 'calibration', 'calibration_design', 'assurance'],
        instruction='Reconcile all operative definitions, schedules, work factors and capacity statements '
                    'with the amended frozen caps. Preserve historical statements as provenance only. '
                    'Do not change the question, experiment, estimators, support minima or frozen caps. '
                    'Explain each dependent change; native checks and independent review remain required.',
        scientific_approval=False, execution_authority=False)
    consistency_key = canonical_digest(consistency)
    value['evidence_catalog'][consistency_key] = consistency
    value['findings_digest'] = consistency_key
    return MethodTaskContract.model_validate(value).model_dump(mode='json')
