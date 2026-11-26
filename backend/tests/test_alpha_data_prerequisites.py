from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import alpha_data_prerequisites as module
from app.services.alpha_disposition import disposition_for
from app.services.graph import digest_document as digest


def packet():
    document = dict(schema_version='method-data-prerequisites-v1', candidate_digest='a'*64,
        source_commit='b'*40, execution_authority=False, checkpoints=[dict(
            catalog_digest='c'*64, dataset_key='panel', layer='curated', venue_id='bybit',
            symbol='ETHUSDT', timeframe='5m', universe_key='reviewed-basket',
            effective_at='2025-01-01T00:00:00Z', known_at='2025-01-01T00:00:00Z')])
    key = digest(document)
    return dict(source_commit='b'*40, dependencies={'data_prerequisites':key}, evidence={key:document})


def test_missing_contract_is_unknown_not_implicit_ready_or_missing_data(monkeypatch):
    resolver = Mock()
    monkeypatch.setattr(module, 'resolve_market_data', resolver)
    with pytest.raises(module.DataPrerequisiteUnavailable) as caught:
        module.require_data_prerequisites(None, {'source_commit':'b'*40}, 'a'*64, [])
    assert caught.value.reason_code == 'assess_method_data_prerequisites'
    assert disposition_for(caught.value.reason_code, caught.value.detail)['automatic_repair'] is False
    resolver.assert_not_called()


@pytest.mark.parametrize('error', [module.MarketDataUnknown, module.ReferenceDataUnknown])
def test_absent_trusted_data_defers_without_paid_repair(monkeypatch, error):
    monkeypatch.setattr(module, 'resolve_market_data', Mock(side_effect=error('unavailable')))
    with pytest.raises(module.DataPrerequisiteUnavailable) as caught:
        module.require_data_prerequisites(None, packet(), 'a'*64, [])
    d = disposition_for(caught.value.reason_code, caught.value.detail)
    assert d['disposition'] == 'await_data'
    assert d['owner'] == 'data_admission'
    assert d['automatic_repair'] is False
    assert caught.value.detail['checkpoint']['universe_key'] == 'reviewed-basket'


def test_registered_resolution_not_caller_attestation_is_used(monkeypatch):
    p = packet()
    original = deepcopy(p)
    resolved = {'catalog_digest':'c'*64, 'catalog_id':'catalog', 'partition':{'content_digest':'d'*64}}
    resolver = Mock(return_value=SimpleNamespace(model_dump=lambda **_: resolved))
    monkeypatch.setattr(module, 'resolve_market_data', resolver)
    bindings = [{'catalog_id':'catalog', 'dataset_key':'panel', 'partition_digests':['d'*64]}]
    result = module.require_data_prerequisites('db', p, 'a'*64, bindings)
    assert result['resolutions'] == [resolved]
    assert result['scientific_certification'] is False
    assert result['execution_authority'] is False
    assert resolver.call_args.args[0] == 'db'
    assert resolver.call_args.args[1].catalog_digest == 'c'*64
    assert p == original
    with pytest.raises(module.DataPrerequisiteUnavailable, match='assess_method_data_prerequisites'):
        module.require_data_prerequisites('db', p, 'a'*64,
            [dict(bindings[0], partition_digests=['e'*64])])


@pytest.mark.parametrize('change', ['digest', 'candidate', 'source', 'assertion'])
def test_invalid_or_unbound_prerequisites_never_reach_resolver(monkeypatch, change):
    p = packet()
    old = p['dependencies']['data_prerequisites']
    doc = p['evidence'][old]
    if change == 'digest': doc['checkpoints'][0]['symbol'] = 'BTCUSDT'
    else:
        if change == 'candidate': doc['candidate_digest'] = 'd'*64
        if change == 'source': doc['source_commit'] = 'd'*40
        if change == 'assertion': doc['listing_verified'] = True
        key = digest(doc); p['evidence'] = {key:doc}; p['dependencies']['data_prerequisites'] = key
    resolver = Mock(); monkeypatch.setattr(module, 'resolve_market_data', resolver)
    with pytest.raises(module.DataPrerequisiteUnavailable):
        module.require_data_prerequisites(None, p, 'a'*64, [])
    resolver.assert_not_called()


def test_producer_is_deterministic_idempotent_and_does_not_rebind_history():
    p = packet()
    checkpoint = next(iter(p['evidence'].values()))['checkpoints'][0]
    contract = {'candidate_digest': 'a'*64, 'base_ref': 'b'*40,
                'dependencies': {}, 'evidence_catalog': {}}
    before = deepcopy(contract)
    bound = module.bind_data_prerequisites(contract, [checkpoint, checkpoint])
    assert contract == before
    key = bound['dependencies']['data_prerequisites']
    assert len(bound['evidence_catalog'][key]['checkpoints']) == 1
    assert module.bind_data_prerequisites(bound, [checkpoint]) == bound
    changed = checkpoint | {'symbol': 'SOLUSDT'}
    with pytest.raises(ValueError, match='explicit successor'):
        module.bind_data_prerequisites(bound, [changed])
    other = module.bind_data_prerequisites(contract, [changed])
    assert other['dependencies']['data_prerequisites'] != key
    assert other['evidence_catalog'][other['dependencies']['data_prerequisites']]['execution_authority'] is False


def test_producer_cannot_assert_no_data_requirements_with_an_empty_list():
    with pytest.raises(ValueError):
        module.bind_data_prerequisites({'candidate_digest':'a'*64, 'base_ref':'b'*40}, [])


def test_real_resolver_preserves_provenance_failure_without_claiming_absent_bars():
    db = Mock()
    db.scalar.return_value = None
    with pytest.raises(module.DataPrerequisiteUnavailable) as caught:
        module.require_data_prerequisites(db, packet(), 'a'*64, [])
    assert caught.value.detail['data_reason_code'] == 'catalog_not_known_at_requested_time'
    assert caught.value.reason_code == 'produce_admitted_method_data'
    assert disposition_for(caught.value.reason_code, caught.value.detail)['automatic_repair'] is False
    db.scalar.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize('reason', [
    'partition_admission_failed', 'source_not_available',
    'membership_not_known_at_requested_clocks',
])
def test_typed_data_failure_survives_deferral(monkeypatch, reason):
    monkeypatch.setattr(module, 'resolve_market_data', Mock(side_effect=
        module.MarketDataUnknown('diagnostic', reason_code=reason)))
    with pytest.raises(module.DataPrerequisiteUnavailable) as caught:
        module.require_data_prerequisites(None, packet(), 'a'*64, [])
    assert caught.value.detail['data_reason_code'] == reason
    assert caught.value.detail['checkpoint']['known_at'] == '2025-01-01T00:00:00Z'


@pytest.mark.parametrize('available', [True, False])
def test_prospective_api_assessment_is_read_only_and_never_approves(monkeypatch, available):
    from uuid import uuid4
    from app.api.routes.alpha_campaign import DataPrerequisiteAssessment, assess_data_prerequisites, router
    from app.core.security import require_orchestrator
    p = packet()
    catalog_id = uuid4()
    binding = dict(dataset_build_id=uuid4(), catalog_id=catalog_id,
        lake_governance_snapshot_id=uuid4(), producer_receipt_id=uuid4(),
        dataset_key='panel', partition_digests=['d'*64],
        evidence_class='live_exchange_history', research_principal='alpha-research-runner')
    payload = DataPrerequisiteAssessment(declaration=next(iter(p['evidence'].values())),
                                         dataset_bindings=[binding])
    db = Mock()
    if available:
        resolver = Mock(return_value=SimpleNamespace(model_dump=lambda **_: {
            'catalog_id':str(catalog_id), 'partition':{'content_digest':'d'*64}}))
        monkeypatch.setattr(module, 'resolve_market_data', resolver)
    else:
        # Exercise the actual resolver's missing-catalog branch.
        db.scalar.return_value = None
    result = assess_data_prerequisites(payload, db)
    assert result['status'] == ('declared_checkpoints_resolved' if available else 'blocked')
    assert result['execution_authority'] is False
    assert result['scientific_certification'] is False
    assert result['declaration_completeness_reviewed'] is False
    if not available:
        assert result['detail']['data_reason_code'] == 'catalog_not_known_at_requested_time'
        assert result['disposition']['automatic_repair'] is False
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()
    route = next(r for r in router.routes if r.path.endswith('/data-prerequisites/assess'))
    assert any(d.call is require_orchestrator for d in route.dependant.dependencies)
