from unittest.mock import MagicMock

import pytest
from app.api.routes.execution_calibration_schemas import router
from app.schemas.execution_calibration_schema import ExecutionCalibrationSchemaCreate
from app.services.execution_calibration_schema import (
    ExecutionCalibrationSchemaConflict,
    digest,
    register_execution_calibration_schema,
)


def specification():
    return {"schema_version": "exec005-execution-calibration-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "execution-quality-calibration",
        "version": "1.0.0",
        "producer": "bt.institutional.execution_calibration.execution_calibration_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec005-pilot",
    }
    values.update(overrides)
    return ExecutionCalibrationSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_execution_calibration_schema(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_execution_calibration_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(ExecutionCalibrationSchemaConflict, match="digest"):
        register_execution_calibration_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(ExecutionCalibrationSchemaConflict, match="immutable"):
        register_execution_calibration_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/execution-calibration-schemas",
        "/v1/research/execution-calibration-schemas/{schema_id}",
    }
