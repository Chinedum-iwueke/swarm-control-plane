"""Non-executing adapter from bounded specification repair to native planning."""
from copy import deepcopy
import re

SCHEMA = 'requirements-method-repair-v1'
TEXT_FIELDS = frozenset({
    'target_equation', 'estimator', 'threshold_rule', 'control_rule',
    'uncertainty_procedure', 'split_and_update_policy', 'missing_data_policy',
    'event_support_rationale', 'falsification_rule',
})
# Target, event definition, controls and splits belong to the frozen experiment.
REPAIR_FIELDS = frozenset({
    'estimator', 'uncertainty_procedure', 'missing_data_policy',
    'event_support_rationale', 'falsification_rule',
})
INPUT_FIELDS = frozenset({
    'discovery_candidate', 'representation_plan', 'dataset_bindings',
    'window', 'validation_requirements',
})


def specification(method):
    if not isinstance(method, dict) or set(method) != (
            TEXT_FIELDS | {'schema_version', 'planning_inputs_digest', 'quantile_support_plan'}):
        raise ValueError('Exact requirements repair field set required')
    if method['schema_version'] != SCHEMA or not re.fullmatch(
            '[a-f0-9]{64}', str(method['planning_inputs_digest'])):
        raise ValueError('Requirements repair requires immutable planning inputs')
    for name in TEXT_FIELDS:
        value = method[name]
        if (not isinstance(value, str) or not 20 <= len(value) <= 4000
                or value.strip().lower() in {'to be determined later', 'not yet specified'}):
            raise ValueError('Incomplete requirements definition: ' + name)
    plans = method['quantile_support_plan']
    if not isinstance(plans, list) or len(plans) > 100:
        raise ValueError('Invalid quantile support plans')
    for item in plans:
        if (not isinstance(item, dict) or set(item) != {
                'gate', 'partition', 'quantile', 'threshold_policy'}
                or not isinstance(item['gate'], str) or not 1 <= len(item['gate']) <= 200
                or item['partition'] not in {'training', 'validation', 'test'}
                or type(item['quantile']) not in {int, float} or not 0 < item['quantile'] < 1
                or item['threshold_policy'] not in {
                    'fixed_training_linear_strict_upper_tail',
                    'fixed_training_linear_strict_lower_tail'}):
            raise ValueError('Invalid quantile support definition')
    return {key: deepcopy(method[key]) for key in TEXT_FIELDS | {'quantile_support_plan'}}


def planning_payload(proposal, catalog, source_commit, digest):
    """Build a prospective diagnostic input, never a reviewed execution package."""
    if set(proposal) != {'scientific_identity', 'support_minima', 'method'}:
        raise ValueError('Exact scientific proposal sections required')
    method = proposal['method']
    revised = specification(method)
    reference = method['planning_inputs_digest']
    document = catalog.get(reference)
    if (not isinstance(document, dict) or digest(document) != reference
            or set(document) != {'schema_version', 'source_commit', 'inputs'}
            or document['schema_version'] != 'requirements-repair-inputs-v1'
            or document['source_commit'] != source_commit):
        raise ValueError('Requirements planning evidence/source mismatch')
    inputs = document['inputs']
    if not isinstance(inputs, dict) or set(inputs) != INPUT_FIELDS:
        raise ValueError('Exact native planning inputs required; no recursive tools or successors')
    candidate = inputs['discovery_candidate']
    if not isinstance(candidate, dict) or not isinstance(inputs['validation_requirements'], dict):
        raise ValueError('Invalid candidate or native requirements package')
    identity = {key: value for key, value in candidate.items() if key != 'scientific_specification'}
    if proposal['scientific_identity'] != identity:
        raise ValueError('Requirements repair changed candidate identity')
    package = inputs['validation_requirements']
    requirements = package.get('requirements')
    if not isinstance(requirements, dict) or proposal['support_minima'] != requirements:
        raise ValueError('Requirements repair changed frozen support minima')
    original = candidate.get('scientific_specification', {})
    for field in (TEXT_FIELDS - REPAIR_FIELDS) | {'quantile_support_plan'}:
        if revised[field] != original.get(field, [] if field == 'quantile_support_plan' else None):
            raise ValueError('Requirements repair changed frozen experiment: ' + field)
    payload = deepcopy(inputs)
    payload['discovery_candidate']['scientific_specification'] = revised
    # A static successor diagnostic cannot inherit an approval of the old method.
    payload['validation_requirements'].pop('review_receipt', None)
    payload['validation_requirements']['scientific_certification'] = False
    return payload



def rebind_for_review(proposal, catalog, clock, source_commit, digest):
    """Derive new review inputs while retaining the parent's immutable preimage."""
    payload = planning_payload(proposal, catalog, source_commit, digest)
    parent = catalog[proposal['method']['planning_inputs_digest']]['inputs']
    if (clock.get('schema_version') != 'admitted-research-clock-v1'
            or clock.get('evidence_digest') != digest({
                key: value for key, value in clock.items() if key != 'evidence_digest'})
            or clock.get('representation_digest') != digest(parent['representation_plan'])
            or clock.get('capital_or_order_authority') is not False):
        raise ValueError('Requirements successor clock custody mismatch')
    parent_basis = digest(dict(candidate=parent['discovery_candidate'],
        clock_digest=clock['evidence_digest'], source_commit=source_commit))
    if parent['validation_requirements']['requirements'].get('basis_digest') != parent_basis:
        raise ValueError('Requirements successor parent basis preimage mismatch')
    coverage = parent['validation_requirements'].get('coverage')
    if (not isinstance(coverage, list) or not coverage
            or any(item.get('eligibility_evidence_digest') != clock['evidence_digest']
                   for item in coverage)):
        raise ValueError('Requirements successor coverage clock mismatch')
    candidate = payload['discovery_candidate']
    basis = digest(dict(candidate=candidate, clock_digest=clock['evidence_digest'],
                        source_commit=source_commit))
    package = payload['validation_requirements']
    package['requirements']['basis_digest'] = basis
    package.pop('native_feasibility_receipt', None)
    lineage = dict(schema_version='requirements-method-successor-lineage-v1',
        parent_candidate_digest=digest(parent['discovery_candidate']),
        successor_candidate_digest=digest(candidate),
        parent_planning_inputs_digest=proposal['method']['planning_inputs_digest'],
        parent_basis_digest=parent_basis, successor_basis_digest=basis,
        clock_digest=clock['evidence_digest'], source_commit=source_commit,
        requires_fresh_native_planning=True, requires_fresh_independent_review=True,
        scientific_approval=False, execution_authority=False)
    return payload, lineage


def verify_ready(report, payload, source_commit, digest):
    """Planning readiness is not scientific adequacy, observed support or approval."""
    if (report.get('schema_version') != 'native-requirements-feasibility-v1'
            or report.get('source_commit') != source_commit
            or report.get('input_digest') != digest(payload)
            or report.get('report_digest') != digest({
                key: value for key, value in report.items() if key != 'report_digest'})
            or report.get('scientific_certification') is not False
            or report.get('execution_authority') is not False):
        raise ValueError('Native requirements report custody mismatch')
    plans = report.get('validation_plans', {})
    if (report.get('status') != 'ready' or report.get('reasons') != []
            or set(plans) != {'smoke', 'scientific'}
            or any(plan.get('status') != 'ready' or plan.get('reasons') != []
                   for plan in plans.values())
            or report.get('coverage_successor_proposal') is not None
            or report.get('successor_validation_plans') is not None):
        raise ValueError('Native requirements are not ready for independent review')
    return report
