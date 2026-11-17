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
