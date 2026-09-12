from unittest.mock import MagicMock

import pytest
from app.api.routes.demo_certification_schemas import router
from app.schemas.demo_certification_schema import DemoCertificationSchemaCreate
from app.services.demo_certification_schema import (
    DemoCertificationSchemaConflict,
    digest,
    register_demo_certification_schema,
)


def specification():
    return {"schema_version": "demo001-production-like-venue-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "production-like-venue-demo-certification",
        "version": "1.0.0",
        "producer": "bt.institutional.demo_certification.demo_certification_receipt",
        "source_commit": "d" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "demo001-pilot",
    }
    values.update(overrides)
    return DemoCertificationSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_demo_certification_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_demo_certification_schema(replay, payload()) is record


def test_rejects_digest_and_immutable_version_drift():
    with pytest.raises(DemoCertificationSchemaConflict, match="digest"):
        register_demo_certification_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(DemoCertificationSchemaConflict, match="immutable"):
        register_demo_certification_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/demo-certification-schemas",
        "/v1/research/demo-certification-schemas/{schema_id}",
    }
