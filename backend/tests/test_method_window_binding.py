from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.services.graph import digest_document as digest
from app.services.method_window_binding import prepare_window_binding


def fixture(minutes=120):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    step = timedelta(minutes=minutes)
    def span(a, b):
        return dict(start=(start+a*step).isoformat(), end=(start+b*step).isoformat())
    proposal = dict(scientific_identity={'question': 'fixture'}, support_minima=dict(
        research_bar_minutes=minutes, feature_warmup_bars=10, target_horizon_bars=2,
        purge_bars=2, embargo_bars=1, minimum_training_bars=20,
        minimum_validation_bars=10, minimum_test_bars=10, smoke_bars=5,
        minimum_scientific_window_days=1), method={})
    plans = {}
    for mode, parts in dict(scientific=dict(feature_warmup=span(0,10), training=span(10,30),
            validation=span(33,43), test=span(46,56), target_tail=span(56,58)),
            smoke=dict(feature_warmup=span(41,51), smoke=span(51,56), target_tail=span(56,58))).items():
        plan = dict(mode=mode, status='ready', reasons=[], source_commit='a'*40,
            coverage_receipt_digests=['b'*64], partitions=parts)
        plans[mode] = plan | {'plan_digest': digest(plan)}
    return proposal, dict(status='ready', source_commit='a'*40,
        execution_authority=False, validation_plans=plans)


def bind(proposal, report):
    return prepare_window_binding(proposal, report, source_commit='a'*40,
        envelope_start='2024-01-01T00:00:00Z', envelope_end='2026-01-01T00:00:00Z')


@pytest.mark.parametrize('minutes', [60, 120, 240])
def test_projection_preserves_identity_history_and_has_no_authority(minutes):
    proposal, report = fixture(minutes)
    before = deepcopy((proposal, report))
    result = bind(proposal, report)
    assert (proposal, report) == before
    assert result['parent_proposal_digest'] == digest(proposal)
    assert result['execution_authority'] is False
    assert result['requires_exact_successor_approval'] is True
    assert result['modes']['scientific']['calendar_capacity_bars']['training'] == 20
    assert not result['modes']['scientific']['eligible_rows_observed']
    assert not result['modes']['scientific']['target_tail_may_generate_decisions']


@pytest.mark.parametrize('mutation', ['source', 'digest', 'clock', 'gap', 'tail', 'capacity', 'envelope', 'coverage'])
def test_invalid_binding_fails_closed(mutation):
    proposal, report = fixture()
    plan = report['validation_plans']['scientific']
    parts = plan['partitions']
    if mutation == 'source': report['source_commit'] = 'c'*40
    elif mutation == 'digest': plan['plan_digest'] = 'd'*64
    elif mutation == 'clock': parts['training']['start'] = '2025-01-01T20:01:00Z'
    elif mutation == 'gap': parts['validation']['start'] = parts['training']['end']
    elif mutation == 'tail': parts['target_tail']['start'] = parts['test']['start']
    elif mutation == 'capacity': proposal['support_minima']['minimum_training_bars'] = 21
    elif mutation == 'envelope': parts['feature_warmup']['start'] = '2023-01-01T00:00:00Z'
    elif mutation == 'coverage': plan['coverage_receipt_digests'] = []
    if mutation != 'digest':
        plan['plan_digest'] = digest({k:v for k,v in plan.items() if k != 'plan_digest'})
    with pytest.raises(ValueError): bind(proposal, report)
