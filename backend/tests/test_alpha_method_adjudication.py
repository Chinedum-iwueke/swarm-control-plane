from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.evaluator_routing import MethodAdjudicationReview, parse_strategy_review
from app.schemas.method_adjudication import validate_adjudication
from app.services.graph import digest_document as digest
from app.services.alpha_method_recovery import correction_contract, RecoveryDeferred
from .test_alpha_method_recovery import rejected


@pytest.mark.parametrize('exhausted', ['deadline', 'tool_calls', 'reserved_work'])
def test_no_adjudication_spend_when_recheck_cannot_run(exhausted):
    from app.services.alpha_method_recovery import require_recovery_capacity
    task, result, _, now = rejected()
    require_recovery_capacity(task, result, now=now)
    if exhausted == 'deadline':
        result['state']['deadline'] = now.timestamp()
    else:
        limit = 'max_tool_calls' if exhausted == 'tool_calls' else 'max_work_units'
        result['state'][exhausted] = task.input_contract['policy'][limit]
    with pytest.raises(RecoveryDeferred):
        require_recovery_capacity(task, result, now=now)


def decision_fixture(decision='recheck'):
    task, result, reviews, now = rejected()
    packet = result['review_packet']
    rejected_reviews = [r.model_dump(mode='json') for r in reviews]
    bundle = {'method_review_packet': packet, 'rejected_reviews': rejected_reviews}
    findings = rejected_reviews[0]['method_verdict']['findings']
    raw = dict(subject_digest='a'*64, verdict='reject', checks=['target'],
        rationale='A synthetic interpretation dispute requires a fresh independent review.',
        blockers=['No scientific approval is issued'], method_adjudication={
            'packet_digest': digest(packet), 'reviews_digest': digest(rejected_reviews),
            'decision': decision, 'finding_evidence': {digest(f): list(packet['evidence']) for f in findings},
            'rationale': 'The retained evidence supports a fresh scope interpretation check.'})
    receipt = dict(schema_version='method-adjudication-receipt-v1', review=raw,
                   prior_packet=packet, scientific_approval=False, execution_authority=False)
    return task, result, reviews, now, bundle, raw, receipt


def test_adjudication_schema_parity_and_no_approval(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.strategy_review_contract import MethodAdjudicationReview as Worker
    from swarm_worker.method_adjudication_contract import validate_adjudication as worker_validate
    *_, bundle, raw, _ = decision_fixture()
    parsed = parse_strategy_review(raw)
    assert isinstance(parsed, MethodAdjudicationReview)
    assert Worker.model_validate(raw).model_dump() == parsed.model_dump()
    validate_adjudication(parsed, bundle, digest)
    worker_validate(Worker.model_validate(raw), bundle, digest)
    with pytest.raises(ValueError):
        parse_strategy_review(raw | {'verdict': 'approve'})


@pytest.mark.parametrize('defect', ['packet', 'reviews', 'missing', 'unrelated', 'duplicate'])
def test_adjudication_cannot_substitute_or_omit_evidence(defect):
    *_, bundle, raw, _ = decision_fixture()
    item = raw['method_adjudication']
    key = next(iter(item['finding_evidence']))
    if defect == 'packet': item['packet_digest'] = '0'*64
    elif defect == 'reviews': item['reviews_digest'] = '0'*64
    elif defect == 'missing': item['finding_evidence'] = {}
    elif defect == 'unrelated': item['finding_evidence'][key] = ['0'*64]
    else: item['finding_evidence'][key] *= 2
    with pytest.raises(ValueError):
        validate_adjudication(parse_strategy_review(raw), bundle, digest)


def test_recheck_preserves_method_budgets_and_requires_new_native_packet():
    task, result, reviews, now, _, _, receipt = decision_fixture()
    before = deepcopy(result)
    raw = correction_contract(task, result, reviews, now=now, adjudication=receipt)
    assert raw['proposal'] == result['state']['proposal']
    assert raw['policy']['max_model_calls'] == task.input_contract['policy']['max_model_calls']
    assert raw['policy']['max_tool_calls'] == task.input_contract['policy']['max_tool_calls'] - 1
    assert raw['evidence_catalog'][raw['findings_digest']]['schema_version'] == 'method-review-recheck-v1'
    retained = next(v for v in raw['evidence_catalog'].values()
                    if v.get('schema_version') == 'method-adjudication-receipt-v1')
    reference = retained['prior_packet_reference']
    assert reference['parent_task_id'] == str(task.id)
    assert reference['parent_result_digest'] == result['result_digest']
    assert reference['packet_digest'] == digest(result['review_packet'])
    restored = {k:v for k,v in retained.items() if k != 'prior_packet_reference'}
    restored['prior_packet'] = result['review_packet']
    assert restored == receipt and digest(restored) == reference['receipt_digest']
    assert not any(v.get('schema_version') == 'native-diagnostic-receipt-v1' for v in raw['evidence_catalog'].values())
    assert result == before
    receipt['review']['method_adjudication']['decision'] = 'disputed'
    with pytest.raises(RecoveryDeferred, match='dispute_unresolved'):
        correction_contract(task, result, reviews, now=now, adjudication=receipt)


def test_adjudication_packet_reference_rejects_substituted_parent():
    task, result, reviews, now, _, _, receipt = decision_fixture()
    receipt['prior_packet'] = {'different': 'packet'}
    with pytest.raises(ValueError, match='prior packet custody'):
        correction_contract(task, result, reviews, now=now, adjudication=receipt)


def test_adjudication_route_excludes_both_reviewers_and_reuses_publication(monkeypatch):
    from app.services import alpha_method_adjudication as module, alpha_method_tasks, alpha_campaign, evaluator_routing
    task, result, reviews, _, _, _, _ = decision_fixture()
    task.input_contract['evidence_catalog'] = {}
    campaign = SimpleNamespace(id=uuid4(), specification={'method_dispute_policy': 'independent_once'})
    def identity():
        return dict(agent_id=str(uuid4()), machine='vm1-developer', provider='codex', model_family='fixture',
                    runtime='fixture', context_group=str(uuid4()), package_digest='a'*64)
    producer, reviewers = identity(), [identity(), identity()]
    original = SimpleNamespace(id=uuid4(), policy={})
    route = SimpleNamespace(id=uuid4(), status='assigned')
    monkeypatch.setattr(alpha_method_tasks, 'require_current_method_authority', lambda *_: None)
    monkeypatch.setattr(alpha_method_tasks, 'current_review_identities', lambda *_, **__: reviewers)
    create = MagicMock(return_value=route)
    monkeypatch.setattr(evaluator_routing, 'create_route', create)
    monkeypatch.setattr(evaluator_routing, 'validated_alpha_strategy_reviews', lambda *_, **__: None)
    monkeypatch.setattr(alpha_campaign, '_materialize_strategy_review_tasks', lambda *_: None)
    events = []
    monkeypatch.setattr(alpha_campaign, '_append_event', lambda *args: events.append(args[-1]))
    db = MagicMock()
    db.scalar.return_value = None
    assert module.adjudicate_method(db, campaign, task, result['review_packet'], producer, original, reviews) == {'pending': True}
    payload = create.call_args.args[1]
    assert payload.required_review_kinds == ['method_adjudication']
    assert {str(p.agent_id) for p in payload.excluded_producers} == {p['agent_id'] for p in reviewers}
    db.scalar.return_value = SimpleNamespace(payload=events[0])
    db.get.return_value = route
    module.adjudicate_method(db, campaign, task, result['review_packet'], producer, original, reviews)
    create.assert_called_once()
    task.input_contract['evidence_catalog'] = {'prior': {'schema_version': 'method-adjudication-receipt-v1'}}
    assert module.adjudicate_method(db, campaign, task, result['review_packet'], producer, original, reviews) is None
