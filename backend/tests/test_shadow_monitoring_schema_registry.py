from unittest.mock import MagicMock

import pytest
from app.api.routes.shadow_monitoring_schemas import router
from app.schemas.shadow_monitoring_schema import ShadowMonitoringSchemaCreate
from app.services.shadow_monitoring_schema import (
    ShadowMonitoringSchemaConflict,
    digest,
    register_shadow_monitoring_schema,
)


def specification():
    return {"schema_version": "shadow002-prospective-monitoring-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "prospective-candidate-monitoring",
        "version": "1.0.0",
        "producer": "bt.institutional.shadow_monitoring.shadow_monitoring_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "shadow002-pilot",
    }
    values.update(overrides)
    return ShadowMonitoringSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_shadow_monitoring_schema(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_shadow_monitoring_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(ShadowMonitoringSchemaConflict, match="digest"):
        register_shadow_monitoring_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(ShadowMonitoringSchemaConflict, match="immutable"):
        register_shadow_monitoring_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/shadow-monitoring-schemas",
        "/v1/research/shadow-monitoring-schemas/{schema_id}",
    }
