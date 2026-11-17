from copy import deepcopy
from pathlib import Path

import pytest

from app.schemas.evaluator_routing import AlphaStrategyReview, MethodStrategyReview, parse_strategy_review
from app.schemas.method_verdict import validate_method_review
from app.services.graph import digest_document as digest


def example():
    evidence = {'assumption': 'synthetic fixture, not empirical support'}
    packet = {'requirements': {'target': 'exact target'}, 'evidence': {digest(evidence): evidence}}
    raw = dict(subject_digest='a'*64, verdict='approve', checks=['target'],
               rationale='Every exact obligation was checked against the supplied evidence.', blockers=[],
               method_verdict=dict(packet_digest=digest(packet), verdict='accept',
                                   checks=['target'], findings=[], rationale='Exact obligation checked.'))
    return packet, raw


def test_legacy_serialization_is_unchanged_and_method_subtype_retained():
    packet, raw = example()
    legacy = {k: v for k, v in raw.items() if k != 'method_verdict'}
    assert parse_strategy_review(legacy).model_dump() == legacy
    assert type(parse_strategy_review(legacy)) is AlphaStrategyReview
    assert isinstance(parse_strategy_review(raw), MethodStrategyReview)
    validate_method_review(parse_strategy_review(raw), packet, digest)


@pytest.mark.parametrize('defect', ['packet', 'omission', 'duplicate', 'contradiction', 'evidence', 'criterion', 'blockers'])
def test_method_review_rejects_substitution_and_unbound_findings(defect):
    packet, raw = example()
    if defect in {'evidence', 'criterion', 'blockers'}:
        raw['verdict'] = 'reject'
        raw['blockers'] = ['Missing justification']
        raw['method_verdict'].update(verdict='reject', findings=[dict(
            criterion='target', evidence_digests=list(packet['evidence']),
            violation='Missing justification', verification='Inspect the supporting evidence')])
    if defect == 'packet':
        raw['method_verdict']['packet_digest'] = '0'*64
    elif defect == 'omission':
        raw['method_verdict']['checks'] = ['other']
    elif defect == 'duplicate':
        raw['method_verdict']['checks'] *= 2
    elif defect == 'contradiction':
        raw['verdict'] = 'reject'
    elif defect == 'evidence':
        raw['method_verdict']['findings'][0]['evidence_digests'] = ['0'*64]
    elif defect == 'criterion':
        raw['method_verdict']['findings'][0]['criterion'] = 'unrecorded'
    else:
        raw['blockers'] = []
    with pytest.raises(ValueError):
        validate_method_review(parse_strategy_review(raw), packet, digest)


def test_worker_and_api_contracts_agree(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.strategy_review_contract import MethodStrategyReview as Worker
    from swarm_worker.method_verdict_contract import validate_method_review as worker_validate
    packet, raw = example()
    assert Worker.model_validate(raw).model_dump() == MethodStrategyReview.model_validate(raw).model_dump()
    worker_validate(Worker.model_validate(raw), deepcopy(packet), digest)
