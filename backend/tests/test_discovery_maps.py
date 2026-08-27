from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.discovery import router
from app.schemas.discovery import DiscoveryMapCreate, DiscoveryMapDocument
from app.services.discovery import (
    DiscoveryConflict,
    register_discovery_map,
    semantic_fingerprint,
)
from app.services.research import record_digest
from pydantic import ValidationError

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def document(stage="observation", **updates) -> DiscoveryMapDocument:
    value = {
        "schema_version": 1,
        "stage": stage,
        "source_daily_cycle_id": uuid4(),
        "question": "Does weekend liquidity alter next-period BTC momentum returns?",
        "population": {
            "instruments": ["crypto:btc-usdt-perpetual"],
            "venue_keys": ["binance"],
            "start_at": NOW - timedelta(days=365),
            "end_at": NOW,
            "timeframe": "1h",
            "data_catalog_digest": "a" * 64,
            "lake_admission_event_digest": "b" * 64,
        },
        "baseline_definition": "All non-weekend observations in the same regime",
        "effect": {
            "metric": "net-return-bps",
            "estimate": 2.5,
            "baseline": 1.0,
            "incremental_estimate": 1.5,
            "sample_size": 500,
            "unit": "bps",
        },
        "uncertainty": {
            "method": "block-bootstrap",
            "lower": -0.5,
            "upper": 3.5,
            "confidence_level": 0.95,
        },
        "evidence_object_ids": [uuid4()],
        "evidence_digests": ["c" * 64],
        "regime_controls": ["btc-volatility-quintile"],
        "limitations": ["observational evidence does not establish a mechanism"],
    }
    value.update(updates)
    return DiscoveryMapDocument.model_validate(value)


def anomaly(**updates) -> DiscoveryMapDocument:
    value = {
        "null_controls": [
            {
                "control_key": "weekday-permutation",
                "kind": "permutation",
                "result": "passed",
                "evidence_digest": "d" * 64,
            }
        ]
    }
    value.update(updates)
    return document("anomaly", **value)


def opportunity(**updates) -> DiscoveryMapDocument:
    value = {
        "evidence_object_ids": [uuid4(), uuid4()],
        "evidence_digests": ["c" * 64, "e" * 64],
        "null_controls": [
            {
                "control_key": "weekday-permutation",
                "kind": "permutation",
                "result": "passed",
                "evidence_digest": "d" * 64,
            }
        ],
        "mechanism": "Reduced weekend depth amplifies price response to directional flow.",
        "rival_explanations": [
            "The effect is explained only by volatility clustering."
        ],
        "falsification_criteria": ["The effect vanishes after depth matching."],
        "costs": {
            "gross_effect": 2.5,
            "transaction_cost": 0.5,
            "financing_cost": 0.2,
            "impact_cost": 0.3,
            "net_effect": 1.5,
            "unit": "bps",
        },
    }
    value.update(updates)
    return document("opportunity", **value)


def payload(value: DiscoveryMapDocument, **updates) -> DiscoveryMapCreate:
    base = {
        "map_key": "DISC002-WEEKEND-R1",
        "document": value,
        "map_digest": record_digest(value),
        "registered_by": "disc002-pilot",
    }
    base.update(updates)
    return DiscoveryMapCreate.model_validate(base)


def test_observation_and_anomaly_remain_distinct() -> None:
    observation = document()
    assert observation.stage == "observation"
    mapped = anomaly()
    assert mapped.stage == "anomaly"
    assert mapped.costs is None


def test_anomaly_requires_a_passing_null_control() -> None:
    with pytest.raises(ValidationError, match="null controls"):
        document("anomaly")


def test_opportunity_requires_mechanism_independent_evidence_and_costs() -> None:
    mapped = opportunity()
    assert mapped.costs.net_effect == 1.5
    with pytest.raises(ValidationError, match="independent incremental evidence"):
        opportunity(evidence_object_ids=[uuid4()], evidence_digests=["c" * 64])


def test_cost_erased_effect_cannot_be_opportunity() -> None:
    with pytest.raises(ValidationError, match="cost-erased"):
        opportunity(
            costs={
                "gross_effect": 1.0,
                "transaction_cost": 0.5,
                "financing_cost": 0.2,
                "impact_cost": 0.3,
                "net_effect": 0.0,
                "unit": "bps",
            }
        )


def test_semantic_duplicate_is_rejected() -> None:
    value = anomaly()
    existing = SimpleNamespace(id=uuid4(), status="active")
    db = MagicMock()
    db.get.return_value = SimpleNamespace()
    db.scalar.side_effect = [
        SimpleNamespace(),
        SimpleNamespace(event_type="admission_decision", detail={"allowed": True}),
        existing,
    ]
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(content_digest="c" * 64, producer={"agent": "one"})
    ]
    with pytest.raises(DiscoveryConflict, match="semantic duplicate"):
        register_discovery_map(db, payload(value))
    assert len(semantic_fingerprint(value)) == 64


def test_independent_cost_adjusted_opportunity_is_registered() -> None:
    value = opportunity()
    db = MagicMock()
    db.get.return_value = SimpleNamespace()
    db.scalar.side_effect = [
        SimpleNamespace(),
        SimpleNamespace(event_type="admission_decision", detail={"allowed": True}),
        None,
        None,
    ]
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(content_digest="c" * 64, producer={"agent": "one"}),
        SimpleNamespace(content_digest="e" * 64, producer={"agent": "two"}),
    ]
    record = register_discovery_map(db, payload(value))
    assert record.stage == "opportunity"
    assert record.status == "active"
    assert db.add.call_count == 2


def test_supersession_is_append_only_and_marks_prior() -> None:
    value = anomaly()
    prior = SimpleNamespace(id=uuid4(), status="active", event_digest=None)
    db = MagicMock()
    db.get.return_value = SimpleNamespace()
    db.scalar.side_effect = [
        SimpleNamespace(),
        SimpleNamespace(event_type="admission_decision", detail={"allowed": True}),
        prior,
        prior,
        None,
        None,
    ]
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(content_digest="c" * 64, producer={"agent": "one"})
    ]
    record = register_discovery_map(
        db,
        payload(
            value,
            map_key="DISC002-WEEKEND-R2",
            supersedes_map_id=prior.id,
        ),
    )
    assert record.supersedes_map_id == prior.id
    assert prior.status == "superseded"
    assert db.add.call_count == 3


def test_map_digest_and_protected_payload_fail_closed() -> None:
    value = anomaly()
    db = MagicMock()
    with pytest.raises(DiscoveryConflict, match="digest"):
        register_discovery_map(db, payload(value, map_digest="f" * 64))
    raw = value.model_dump()
    raw["protected_market_payload"] = [1, 2, 3]
    with pytest.raises(ValidationError, match="Extra inputs"):
        DiscoveryMapDocument.model_validate(raw)


def test_routes_expose_map_replay_and_event_chain() -> None:
    paths = {route.path for route in router.routes}
    assert "/v1/research/discovery-maps" in paths
    assert "/v1/research/discovery-maps/{map_id}" in paths
    assert "/v1/research/discovery-maps/{map_id}/events" in paths


def test_pilot_consumes_canonical_evidence_object_identity() -> None:
    source = Path("worker/scripts/disc002_pilot.py").read_text(encoding="utf-8")
    assert 'item["object_id"]' in source
    assert 'item["id"] for item in selected' not in source
