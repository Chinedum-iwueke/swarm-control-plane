from unittest.mock import MagicMock

import pytest
from app.api.routes.execution_safety_schemas import router
from app.schemas.execution_safety_schema import ExecutionSafetySchemaCreate
from app.services.execution_safety_schema import (
    ExecutionSafetySchemaConflict,
    digest,
    register_execution_safety_schema,
)


def specification():
    return {"schema_version": "exec007-runtime-safety-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "runtime-freeze-kill-human-recovery",
        "version": "1.0.0",
        "producer": "bt.institutional.runtime_safety.runtime_safety_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec007-pilot",
    }
    values.update(overrides)
    return ExecutionSafetySchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_execution_safety_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_execution_safety_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(ExecutionSafetySchemaConflict, match="digest"):
        register_execution_safety_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(ExecutionSafetySchemaConflict, match="immutable"):
        register_execution_safety_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/execution-safety-schemas",
        "/v1/research/execution-safety-schemas/{schema_id}",
    }
