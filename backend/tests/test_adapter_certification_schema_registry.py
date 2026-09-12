from unittest.mock import MagicMock

import pytest

from app.api.routes.adapter_certification_schemas import router
from app.schemas.adapter_certification_schema import AdapterCertificationSchemaCreate
from app.services.adapter_certification_schema import (
    AdapterCertificationSchemaConflict,
    digest,
    register_adapter_certification_schema,
)


def specification():
    return {"schema_version": "exec008-adapter-certification-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "venue-adapter-certification-and-demo-parity",
        "version": "1.0.0",
        "producer": "bt.institutional.adapter_certification.adapter_certification_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec008-pilot",
    }
    values.update(overrides)
    return AdapterCertificationSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_adapter_certification_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_adapter_certification_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(AdapterCertificationSchemaConflict, match="digest"):
        register_adapter_certification_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(AdapterCertificationSchemaConflict, match="immutable"):
        register_adapter_certification_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/adapter-certification-schemas",
        "/v1/research/adapter-certification-schemas/{schema_id}",
    }
