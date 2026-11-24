from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.evaluator_routing import MethodStrategyReview
from app.services import alpha_method_recovery as recovery
from app.services.graph import digest_document as digest
from .test_alpha_method_tasks import ready_task


def test_accepted_handoff_indexes_only_unreferenced_correction_history():
    task = ready_task()
    result = task.result['summary']['method_episode']
    correction = dict(changes={'estimator_id':'historical'}, addressed_findings=['old'], rationale='old proposal')
    key = digest(correction)
    result['review_packet']['evidence'][key] = deepcopy(correction)
    result['state']['evidence'][key] = deepcopy(correction)
    before = deepcopy(result)
    catalog = recovery.accepted_handoff_catalog(task, result)
    assert result == before and key not in catalog
    index = next(v for v in catalog.values() if v.get('schema_version') == 'method-prior-corrections-index-v1')
    assert index['parent_task_id'] == str(task.id)
    assert index['parent_result_digest'] == result['result_digest']
    assert index['documents'] == [{'digest':key, 'location':'review_packet/evidence/' + key}]
    assert catalog.keys() - {digest(index)} == result['review_packet']['evidence'].keys() - {key}
    assert not index['scientific_approval'] and not index['execution_authority']
    result['review_packet']['requirements']['reference'] = 'Retain scientific definition ' + key
    assert key in recovery.accepted_handoff_catalog(task, result)
    result['review_packet']['requirements'].pop('reference')
    result['state']['evidence'] = deepcopy(result['state']['evidence'])
    result['state']['evidence'][key] = {'tampered':True}
    with pytest.raises(ValueError, match='custody'):
        recovery.accepted_handoff_catalog(task, result)


def test_accepted_handoff_indexes_nested_history_without_rewriting_custody():
    task = ready_task()
    result = task.result['summary']['method_episode']
    archive = {'schema_version': 'method-review-correction-v1', 'reviews': []}
    for _ in range(12):
        archive = {'schema_version': 'method-historical-commissioning-archive-v1',
                   'documents': {digest(archive): archive}}
    key = digest(archive)
    result['review_packet']['evidence'][key] = deepcopy(archive)
    result['state']['evidence'][key] = deepcopy(archive)
    before = deepcopy(result)
    catalog = recovery.accepted_handoff_catalog(task, result)
    assert result == before and key not in catalog
    index = next(v for v in catalog.values()
                 if v.get('schema_version') == 'method-prior-corrections-index-v1')
    assert {'digest': key, 'location': 'review_packet/evidence/' + key} in index['documents']
    assert result['review_packet']['evidence'][key] == archive
    result['review_packet']['requirements']['history_dependency'] = key
    assert recovery.accepted_handoff_catalog(task, result)[key] == archive
    result['review_packet']['requirements'].pop('history_dependency')
    result['state']['evidence'] = deepcopy(result['state']['evidence'])
    result['state']['evidence'][key] = {'changed': True}
    with pytest.raises(ValueError, match='custody'):
        recovery.accepted_handoff_catalog(task, result)


def test_historical_catalog_compaction_preserves_science_and_exact_history():
    docs = [dict(schema_version='scientific-evidence-v1', ordinal=i) for i in range(14)]
    docs += [dict(schema_version='method-explicit-commissioning-successor-v1', ordinal=i)
             for i in range(3)]
    catalog = {digest(doc): doc for doc in docs}
    before = deepcopy(catalog)
    packed = recovery.compact_historical_catalog(catalog)
    assert len(packed) == 15
    assert catalog == before
    archive = next(v for v in packed.values() if v.get('documents'))
    assert not archive['execution_authority'] and not archive['scientific_approval']
    restored = {k:v for k,v in packed.items() if v is not archive} | archive['documents']
    assert restored == catalog
    assert all(digest(v) == k for k,v in restored.items())
    assert recovery.compact_historical_catalog(packed) == packed
    protected = {digest(doc) for doc in docs[-3:]}
    assert recovery.compact_historical_catalog(catalog, protected=protected) == catalog
    corrupt = dict(catalog); corrupt[next(iter(corrupt))] = {'modified': True}
    with pytest.raises(ValueError, match='digest'):
        recovery.compact_historical_catalog(corrupt)


def test_compaction_can_pack_existing_archive_without_losing_nested_custody():
    nested = {'schema_version': 'method-historical-commissioning-archive-v1',
              'documents': {'retained-location': {'old': 'metadata'}}}
    scope = {'schema_version': 'method-commissioning-scope-v1', 'parent': 'old'}
    science = [{'schema_version': 'scientific-evidence-v1', 'ordinal': i} for i in range(15)]
    catalog = {digest(v):v for v in [*science, nested, scope]}
    packed = recovery.compact_historical_catalog(catalog)
    assert len(packed) == 16
    archive = next(v for v in packed.values() if 'documents' in v)
    assert archive['documents'][digest(nested)] == nested
    assert archive['documents'][digest(scope)] == scope
    assert {k:v for k,v in packed.items() if v is not archive} | archive['documents'] == catalog
    assert recovery.compact_historical_catalog(catalog, protected={digest(nested)}) == catalog


def rejected():
    task = ready_task()
    now = datetime.now(timezone.utc)
    task.started_at = now - timedelta(seconds=20)
    result = task.result['summary']['method_episode']
    result['state']['deadline'] = (now + timedelta(seconds=900)).timestamp()
    packet = result['review_packet']
    review = MethodStrategyReview(subject_digest='f'*64, verdict='reject',
        rationale='The estimator definition is ambiguous in this synthetic fixture.',
        checks=['target'], blockers=['Ambiguous estimator'],
        method_verdict=dict(packet_digest=digest(packet), verdict='reject', checks=['target'],
            findings=[dict(criterion='target', evidence_digests=list(packet['evidence']),
                           violation='Ambiguous estimator', verification='Check the estimator definition')],
            rationale='Synthetic fixture rejection.'))
    return task, result, [review], now


def test_review_correction_conserves_budget_identity_deadline_and_citations():
    task, result, reviews, now = rejected()
    before = deepcopy(task.input_contract)
    corrected = recovery.correction_contract(task, result, reviews, now=now)
    assert task.input_contract == before
    assert corrected['proposal'] == result['state']['proposal']
    assert corrected['policy']['max_tool_calls'] == before['policy']['max_tool_calls'] - 1
    assert corrected['policy']['max_work_units'] == before['policy']['max_work_units'] - result['state']['reserved_work']
    assert corrected['policy']['max_duration_seconds'] <= 900
    assert datetime.fromisoformat(corrected['valid_until']).timestamp() <= result['state']['deadline']
    assert set(result['review_packet']['evidence']) <= corrected['evidence_catalog'].keys()
    report = corrected['evidence_catalog'][corrected['findings_digest']]
    assert report['parent_task_id'] == str(task.id)
    assert report['scientific_approval'] is False


@pytest.mark.parametrize('schema', ['method-review-correction-v1', 'method-explicit-commissioning-successor-v1'])
def test_v2_successor_preserves_referenced_definition_documents(schema):
    task, result, reviews, now = rejected()
    definition = {'schema_version': schema, 'definition': 'Synthetic retained definition for regression testing.'}
    reference = digest(definition)
    method = task.input_contract['proposal']['method']
    method.update(schema_version='design-adequacy-contract-v2', experiment={}, calibration_design={},
        calibration={'max_work_units': 100}, assurance={'required_outputs': ['target'],
            'definitions': [{'id': 'target', 'evidence_digest': reference, 'pointer': '/definition'}],
            'workload': {'caps': {'statistic_evaluation': 100}}})
    result['state']['proposal']['method'] = deepcopy(method)
    packet = result['review_packet']
    packet['proposal'] = deepcopy(result['state']['proposal'])
    packet['evidence'][reference] = definition
    for index in range(15):
        historical = {'schema_version': 'method-explicit-commissioning-successor-v1', 'ordinal': index}
        packet['evidence'][digest(historical)] = historical
    reviews[0].method_verdict.packet_digest = digest(packet)
    corrected = recovery.correction_contract(task, result, reviews, now=now)
    assert corrected['evidence_catalog'][reference] == definition
    assert len(corrected['evidence_catalog']) <= 16


def test_diagnostic_successor_retains_spend_and_does_not_recover_unknown_failures():
    task, result, _, now = rejected()
    from app.contracts.native_design_shape import defects
    state = result['state']
    state.update(status='blocked', reason='invalid_stage_result', repairs=1, model_calls=1)
    allowed = sorted(defects(state['proposal']['method']))
    task.input_contract['policy']['allowed_method_fields'] = allowed
    corrected = recovery.diagnostic_correction_contract(task, result, now=now)
    assert corrected['proposal'] == state['proposal']
    assert corrected['policy']['max_model_calls'] == task.input_contract['policy']['max_model_calls'] - 1
    assert corrected['policy']['max_repairs'] == task.input_contract['policy']['max_repairs'] - 1
    assert datetime.fromisoformat(corrected['valid_until']).timestamp() <= state['deadline']
    state['reason'] = 'unknown_infrastructure_error'
    with pytest.raises(ValueError, match='wire-shape'):
        recovery.diagnostic_correction_contract(task, result, now=now)
    state['reason'] = 'invalid_stage_result'
    state['model_calls'] = task.input_contract['policy']['max_model_calls']
    with pytest.raises(recovery.RecoveryDeferred, match='budget_exhausted'):
        recovery.diagnostic_correction_contract(task, result, now=now)


def test_native_shape_contract_parity():
    from pathlib import Path
    root = Path(__file__).parents[2]
    assert (root/'backend/app/contracts/native_design_shape.py').read_text() == (root/'worker/src/swarm_worker/native_design_shape.py').read_text()


@pytest.mark.parametrize('limit', ['repairs', 'model_calls', 'tool_calls', 'reserved_work', 'deadline'])
def test_review_correction_cannot_reset_exhausted_budgets(limit):
    task, result, reviews, now = rejected()
    mapping = {'repairs': 'max_repairs', 'model_calls': 'max_model_calls',
               'tool_calls': 'max_tool_calls', 'reserved_work': 'max_work_units'}
    result['state'][limit] = now.timestamp()-1 if limit == 'deadline' else task.input_contract['policy'][mapping[limit]]
    with pytest.raises(recovery.RecoveryDeferred):
        recovery.correction_contract(task, result, reviews, now=now)


def test_recorded_successor_reuses_exact_task_and_rejects_contract_tampering():
    parent, _, _, _ = rejected()
    successor = SimpleNamespace(id=uuid4(), parent_task_id=parent.id,
                                task_type='alpha_method_design', input_contract={'frozen': True})
    event = SimpleNamespace(payload={'task_id': str(successor.id), 'contract': {'frozen': True},
                                     'contract_digest': digest({'frozen': True})})
    db = MagicMock()
    db.scalar.return_value = event
    db.get.return_value = successor
    campaign = SimpleNamespace(id=uuid4())
    assert recovery.recorded_successor(db, campaign, parent) is successor
    successor.input_contract['frozen'] = False
    with pytest.raises(ValueError, match='lineage changed'):
        recovery.recorded_successor(db, campaign, parent)


def test_duplicate_materialization_checks_authority_under_lock_without_new_work(monkeypatch):
    parent, result, reviews, _ = rejected()
    campaign = SimpleNamespace(id=uuid4())
    db = MagicMock()
    successor = SimpleNamespace(id=uuid4())
    authority = MagicMock()
    monkeypatch.setattr('app.services.alpha_method_tasks.require_current_method_authority', authority)
    monkeypatch.setattr(recovery, 'recorded_successor', lambda *args: successor)
    persist = MagicMock()
    monkeypatch.setattr(recovery, 'persist_new_task', persist)
    assert recovery.materialize_correction(db, campaign, parent, result, reviews) is successor
    db.execute.assert_called_once()
    authority.assert_called_once_with(db, parent)
    persist.assert_not_called()


def test_tampered_lineage_denies_authority(monkeypatch):
    parent, _, _, _ = rejected()
    parent.task_type = 'alpha_method_design'
    child = SimpleNamespace(id=uuid4(), parent_task_id=parent.id,
                            input_contract={'candidate_id': 'test'})
    campaign = SimpleNamespace(specification={'method_design_requests': {}})
    db = MagicMock()
    db.get.return_value = parent
    def tampered(*args):
        raise ValueError('Method correction lineage changed')
    monkeypatch.setattr(recovery, 'recorded_successor', tampered)
    assert recovery.authorized_successor(db, campaign, child) is False


def test_revocation_blocks_even_existing_correction(monkeypatch):
    from fastapi import HTTPException
    parent, result, reviews, _ = rejected()
    def revoked(*args):
        raise HTTPException(409, 'Method episode authority revoked')
    monkeypatch.setattr('app.services.alpha_method_tasks.require_current_method_authority', revoked)
    lookup = MagicMock()
    monkeypatch.setattr(recovery, 'recorded_successor', lookup)
    with pytest.raises(HTTPException):
        recovery.materialize_correction(MagicMock(), SimpleNamespace(id=uuid4()), parent, result, reviews)
    lookup.assert_not_called()
