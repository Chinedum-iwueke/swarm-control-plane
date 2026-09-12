from unittest.mock import MagicMock

import pytest
from app.api.routes.oms_schemas import router
from app.schemas.oms_schema import OmsSchemaCreate
from app.services.oms_schema import OmsSchemaConflict, digest, register_oms_schema


def specification():
    return {"schema_version": "exec004-oms-reconciliation-v1.0.0"}


def payload(**overrides):
    values = {"name": "idempotent-oms-reconciliation", "version": "1.0.0", "producer": "bt.institutional.oms.oms_reconciliation_receipt", "source_commit": "a" * 40, "specification_digest": digest(specification()), "specification": specification(), "status": "active", "registered_by": "exec004-pilot"}
    values.update(overrides)
    return OmsSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_oms_schema(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_oms_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(OmsSchemaConflict, match="digest"):
        register_oms_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(OmsSchemaConflict, match="immutable"):
        register_oms_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {"/v1/research/oms-schemas", "/v1/research/oms-schemas/{schema_id}"}
