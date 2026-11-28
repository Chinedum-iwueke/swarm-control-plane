from copy import deepcopy
from pathlib import Path

import pytest

from app.contracts import requirements_repair as adapter
from app.services.graph import digest_document as digest


def fixture():
    from .test_alpha_requirements_handoff import inputs
    evidence, _, _ = inputs()
    evidence['window'] = {'start': '2025-01-01', 'end': '2026-01-01'}
    evidence.pop('selected_panel_admission')
    evidence['validation_requirements'] = {
        'requirements': deepcopy(evidence['discovery_candidate']['scientific_requirements']),
        'review_receipt': {'old_approval': True},
    }
    document = {'schema_version': 'requirements-repair-inputs-v1',
                'source_commit': 'a'*40, 'inputs': evidence}
    key = digest(document)
    candidate = evidence['discovery_candidate']
    proposal = {
        'scientific_identity': {k: deepcopy(v) for k, v in candidate.items()
                                if k != 'scientific_specification'},
        'support_minima': deepcopy(evidence['validation_requirements']['requirements']),
        'method': {**candidate['scientific_specification'],
                   'schema_version': adapter.SCHEMA, 'planning_inputs_digest': key,
                   'quantile_support_plan': []},
    }
    return proposal, {key: document}


def test_native_payload_preserves_frozen_experiment_and_discards_old_approval(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker import requirements_repair as worker
    proposal, catalog = fixture()
    proposal['method']['uncertainty_procedure'] = 'Revised uncertainty procedure with evidence and fixed preregistration.'
    before = deepcopy((proposal, catalog))
    payload = adapter.planning_payload(proposal, catalog, 'a'*40, digest)
    assert payload == worker.planning_payload(proposal, catalog, 'a'*40, digest)
    assert (proposal, catalog) == before
    assert payload['validation_requirements']['requirements'] == proposal['support_minima']
    assert 'review_receipt' not in payload['validation_requirements']
    assert payload['validation_requirements']['scientific_certification'] is False
    assert payload['discovery_candidate']['scientific_specification']['uncertainty_procedure'].startswith('Revised')
    assert 'calibration' not in proposal['method']
    assert worker.REPAIR_FIELDS == adapter.REPAIR_FIELDS


def test_requirements_contract_and_api_accept_exact_planning_without_calibration(monkeypatch):
    from .test_alpha_method_tasks import fixture as task_fixture, ready_task
    from app.schemas.method_task import MethodTaskContract
    from app.services.alpha_method_tasks import verified_method_result
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    proposal, catalog = fixture()
    raw = task_fixture()[4]
    raw.update(proposal=proposal, evidence_catalog=catalog, base_ref='a'*40,
               diagnostic='requirements_feasibility_v1')
    raw['policy']['allowed_method_fields'] = ['uncertainty_procedure', 'event_support_rationale']
    assert MethodTaskContract.model_validate(raw).model_dump(mode='json') == WorkerContract.model_validate(raw).model_dump(mode='json')
    task = ready_task(raw=raw, projected=True)
    result = verified_method_result(task)
    assert result['state']['status'] == 'ready_for_independent_review'
    assert result['scientific_approval'] is result['execution_authority'] is False
    for field in ['target_equation', 'threshold_rule', 'calibration']:
        raw['policy']['allowed_method_fields'] = [field]
        with pytest.raises(ValueError, match='repair scope'):
            MethodTaskContract.model_validate(raw)


@pytest.mark.parametrize('defect', [None, 'display_card', 'source', 'clock', 'coverage'])
def test_rebinding_retains_science_but_never_inherits_old_receipts(monkeypatch, defect):
    from app.services.alpha_requirements_handoff import requirements_basis_lineage
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker import requirements_repair as worker
    proposal, catalog = fixture()
    document = deepcopy(next(iter(catalog.values())))
    inputs = document['inputs']
    clock = dict(schema_version='admitted-research-clock-v1',
        representation_digest=digest(inputs['representation_plan']), capital_or_order_authority=False)
    clock['evidence_digest'] = digest(clock)
    package = inputs['validation_requirements']
    package['requirements']['basis_digest'] = digest(dict(candidate=inputs['discovery_candidate'],
        clock_digest=clock['evidence_digest'], source_commit='a'*40))
    package['coverage'] = [{'eligibility_evidence_digest': clock['evidence_digest']}]
    package['native_feasibility_receipt'] = {'historical_only': True}
    if defect == 'display_card':
        inputs['discovery_candidate']['dataset_binding_scope'] = 'review_artifact_bundle.dataset_bindings'
        proposal['scientific_identity']['dataset_binding_scope'] = 'review_artifact_bundle.dataset_bindings'
    if defect == 'coverage': package['coverage'][0]['eligibility_evidence_digest'] = 'f'*64
    if defect == 'clock': clock['representation_digest'] = 'f'*64
    reference = digest(document)
    catalog = {reference: document}
    proposal['support_minima'] = deepcopy(package['requirements'])
    proposal['method']['planning_inputs_digest'] = reference
    proposal['method']['uncertainty_procedure'] = 'Revised uncertainty definition without changing the frozen scientific experiment.'
    source = 'b'*40 if defect == 'source' else 'a'*40
    before = deepcopy((proposal, catalog, clock))
    if defect:
        with pytest.raises(ValueError):
            adapter.rebind_for_review(proposal, catalog, clock, source, digest)
        return
    payload, lineage = adapter.rebind_for_review(proposal, catalog, clock, source, digest)
    assert (payload, lineage) == worker.rebind_for_review(proposal, catalog, clock, source, digest)
    assert (proposal, catalog, clock) == before
    assert lineage['parent_basis_digest'] != lineage['successor_basis_digest']
    assert lineage['parent_candidate_digest'] != lineage['successor_candidate_digest']
    current = payload['validation_requirements']
    assert 'review_receipt' not in current and 'native_feasibility_receipt' not in current
    assert {k:v for k,v in current['requirements'].items() if k != 'basis_digest'} == {
        k:v for k,v in package['requirements'].items() if k != 'basis_digest'}
    assert payload['window'] == inputs['window']
    assert payload['dataset_bindings'] == inputs['dataset_bindings']
    verified = requirements_basis_lineage(payload['discovery_candidate'], current, clock, source)
    assert verified['coverage_bound_basis_digest'] == lineage['successor_basis_digest']
    assert lineage['requires_fresh_native_planning'] and lineage['requires_fresh_independent_review']
    assert not lineage['scientific_approval'] and not lineage['execution_authority']


@pytest.mark.parametrize('field', sorted(adapter.TEXT_FIELDS - adapter.REPAIR_FIELDS))
def test_repair_cannot_change_frozen_scientific_definition(field):
    proposal, catalog = fixture()
    proposal['method'][field] = 'Changed scientific experiment, not a permitted method correction.'
    with pytest.raises(ValueError, match='frozen experiment'):
        adapter.planning_payload(proposal, catalog, 'a'*40, digest)


@pytest.mark.parametrize('defect', ['identity', 'minima', 'source', 'custody', 'quantiles', 'recursive'])
def test_repair_rejects_scope_and_custody_changes(defect):
    proposal, catalog = fixture()
    if defect == 'identity': proposal['scientific_identity']['question'] = 'new question'
    if defect == 'minima': proposal['support_minima']['minimum_test_bars'] = 1
    if defect == 'source': source = 'b'*40
    else: source = 'a'*40
    if defect == 'custody': next(iter(catalog.values()))['source_commit'] = 'b'*40
    if defect == 'quantiles':
        proposal['method']['quantile_support_plan'] = [dict(gate='test_events', partition='test',
            quantile=.95, threshold_policy='fixed_training_linear_strict_upper_tail')]
    if defect == 'recursive':
        document = next(iter(catalog.values()))
        document['inputs']['diagnostic_request'] = {}
        key = digest(document)
        catalog = {key: document}
        proposal['method']['planning_inputs_digest'] = key
    with pytest.raises(ValueError):
        adapter.planning_payload(proposal, catalog, source, digest)


@pytest.mark.parametrize('defect', [None, 'source', 'input', 'report_digest', 'authority',
                                  'scientific', 'deferred', 'successor', 'missing_plan'])
def test_ready_means_only_exact_static_planning_readiness(defect):
    proposal, catalog = fixture()
    payload = adapter.planning_payload(proposal, catalog, 'a'*40, digest)
    report = dict(schema_version='native-requirements-feasibility-v1',
        source_commit='a'*40, input_digest=digest(payload), status='ready', reasons=[],
        validation_plans={mode: dict(status='ready', reasons=[]) for mode in ['smoke', 'scientific']},
        scientific_certification=False, execution_authority=False,
        coverage_successor_proposal=None, successor_validation_plans=None)
    if defect == 'source': report['source_commit'] = 'b'*40
    if defect == 'input': report['input_digest'] = 'b'*64
    if defect == 'authority': report['execution_authority'] = True
    if defect == 'scientific': report['scientific_certification'] = True
    if defect == 'deferred': report['status'] = 'deferred'
    if defect == 'successor': report['coverage_successor_proposal'] = {'status': 'proposed'}
    if defect == 'missing_plan': report['validation_plans'].pop('smoke')
    report['report_digest'] = digest(report)
    if defect == 'report_digest': report['report_digest'] = 'c'*64
    if defect:
        with pytest.raises(ValueError):
            adapter.verify_ready(report, payload, 'a'*40, digest)
    else:
        assert adapter.verify_ready(report, payload, 'a'*40, digest) == report
