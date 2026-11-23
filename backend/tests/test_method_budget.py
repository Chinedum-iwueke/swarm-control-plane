from copy import deepcopy
from pathlib import Path

import pytest

from app.contracts.method_budget import bind_prospective_budget
from app.schemas.method_task import MethodTaskContract, canonical_digest
from .test_alpha_method_tasks import fixture


def contract():
    value = fixture()[4]
    value['proposal']['method'].update(
        schema_version='design-adequacy-contract-v2', experiment={}, calibration_design={},
        calibration={'max_work_units': 100},
        assurance={'required_outputs': ['target'], 'workload': {
            'caps': {'statistic_evaluation': 100, 'ols_fit': 20}, 'stages': []}})
    return value


def test_amendment_freezes_only_explicit_caps_preserving_parent_and_science(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    original = contract()
    before = deepcopy(original)
    successor = bind_prospective_budget(original, {'statistic_evaluation': 500, 'ols_fit': 30})
    assert original == before
    assert successor['proposal']['scientific_identity'] == before['proposal']['scientific_identity']
    assert successor['proposal']['support_minima'] == before['proposal']['support_minima']
    assert successor['proposal']['method']['calibration']['max_work_units'] == 500
    assert successor['policy'] == original['policy']
    assert WorkerContract.model_validate(successor).model_dump(mode='json') == successor
    evidence = successor['evidence_catalog'][successor['dependencies']['prospective_budget_amendment']]
    assert evidence['parent_proposal_digest'] == canonical_digest(original['proposal'])
    assert evidence['execution_authority'] is False
    invalidation = successor['evidence_catalog'][successor['findings_digest']]
    assert invalidation['schema_version'] == 'method-amendment-consistency-v1'
    assert invalidation['proposal_digest'] == canonical_digest(successor['proposal'])
    assert invalidation['amendment_digest'] == successor['dependencies']['prospective_budget_amendment']
    assert invalidation['scientific_approval'] is False
    for model in (WorkerContract, MethodTaskContract):
        stale = deepcopy(successor)
        stale['proposal'] = before['proposal']
        with pytest.raises(ValueError, match='exact initial frozen caps'):
            model.model_validate(stale)
        wrong_mandate = deepcopy(successor)
        wrong_mandate['mandate_digest'] = '9'*64
        with pytest.raises(ValueError, match='mandate'):
            model.model_validate(wrong_mandate)


@pytest.mark.parametrize('caps', [
    {'statistic_evaluation': 500},
    {'statistic_evaluation': True, 'ols_fit': 20},
    {'statistic_evaluation': 10**15+1, 'ols_fit': 20},
])
def test_invalid_amendment_fails_before_registration(caps):
    with pytest.raises(ValueError):
        bind_prospective_budget(contract(), caps)


def test_legacy_contract_roundtrip_is_unchanged():
    original = contract()
    assert MethodTaskContract.model_validate(original).model_dump(mode='json') == original
