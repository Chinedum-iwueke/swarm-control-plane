from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services import alpha_method_handoff as service
from app.services.graph import digest_document as digest


def setup(monkeypatch):
    from app.services import alpha_campaign, alpha_method_tasks, evaluator_routing
    db = MagicMock()
    db.scalar.return_value = None
    campaign = SimpleNamespace(id=uuid4(), campaign_digest='c'*64,
        specification={'bulletproof_source_commit': 'a'*40})
    task = SimpleNamespace(id=uuid4(), status='succeeded', plan_digest='d'*64,
        approval_policy={'campaign_digest': campaign.campaign_digest},
        input_contract={'diagnostic': 'requirements_feasibility_v1', 'base_ref': 'a'*40,
                        'candidate_id': str(uuid4()), 'candidate_digest': 'b'*64,
                        'evidence_catalog': {}, 'dependencies': {}})
    inputs = {'synthetic': True, 'discovery_candidate': {'corrected': True}}
    lineage = {'synthetic': True, 'parent_basis_digest': 'e'*64}
    proposal = {'synthetic': True}
    receipt = {'schema_version': 'native-diagnostic-receipt-v1',
        'subject_digest': digest(proposal),
        'result': {'input_digest': digest(inputs), 'report_digest': 'f'*64}}
    packet = {'proposal': proposal, 'evidence': {digest(receipt): receipt}}
    result = {'state': {'status': 'ready_for_independent_review'},
              'review_packet': packet, 'result_digest': '1'*64}
    verified = MagicMock(return_value=result)
    monkeypatch.setattr(alpha_method_tasks, 'verified_method_result', verified)
    monkeypatch.setattr(evaluator_routing, 'task_producer_identity', lambda *_: {'agent_id': 'producer'})
    reviews = [SimpleNamespace(verdict='approve', model_dump=lambda **_: {'verdict': 'approve', 'kind': 'spec'}),
               SimpleNamespace(verdict='approve', model_dump=lambda **_: {'verdict': 'approve', 'kind': 'causality'})]
    route = SimpleNamespace(id=uuid4(), subject_digest='2'*64)
    monkeypatch.setattr(alpha_method_tasks, 'route_method_review', lambda *_: (route, reviews))
    monkeypatch.setattr(service, 'diagnostic_payload', lambda *_: (inputs, lineage))
    published = []
    def append(*args):
        event = SimpleNamespace(payload=deepcopy(args[-1]))
        published.append(event)
        return event
    monkeypatch.setattr(alpha_campaign, '_append_event', append)
    return db, campaign, task, result, reviews, published, verified


def test_handoff_publishes_once_without_rewriting_or_authorizing(monkeypatch):
    db, campaign, task, result, _, published, verified = setup(monkeypatch)
    before = deepcopy((task.input_contract, campaign.specification, result))
    event = service.publish_requirements_handoff(db, campaign, task)
    db.scalar.return_value = event
    assert service.publish_requirements_handoff(db, campaign, task) is event
    assert len(published) == 1 and verified.call_count == 2
    assert before == (task.input_contract, campaign.specification, result)
    p = event.payload
    assert p['method_review_accepted'] and p['requires_separate_downstream_authority']
    assert not any(p[key] for key in ['scientific_certification', 'engineering_authority', 'execution_authority'])
    assert len(p['review_digests']) == 2
    assert p['inputs']['discovery_candidate']['corrected']
    assert p['parent_candidate_digest'] == task.input_contract['candidate_digest']
    event.payload['source_commit'] = '0'*40
    with pytest.raises(ValueError, match='handoff changed'):
        service.publish_requirements_handoff(db, campaign, task)


@pytest.mark.parametrize('defect', ['source', 'campaign', 'failed', 'deferred', 'reject', 'missing_review', 'clock', 'native'])
def test_handoff_fails_closed_without_new_publication(monkeypatch, defect):
    db, campaign, task, result, reviews, published, _ = setup(monkeypatch)
    if defect == 'source': task.input_contract['base_ref'] = '0'*40
    if defect == 'campaign': task.approval_policy['campaign_digest'] = '0'*64
    if defect == 'failed': task.status = 'failed'
    if defect == 'deferred': result['state']['status'] = 'deferred'
    if defect == 'reject': reviews[0].verdict = 'reject'
    if defect == 'missing_review': reviews.pop()
    if defect == 'clock': monkeypatch.setattr(service, 'diagnostic_payload', lambda *_: ({}, None))
    if defect == 'native': result['review_packet']['evidence'] = {}
    with pytest.raises(ValueError):
        service.publish_requirements_handoff(db, campaign, task)
    assert not published
