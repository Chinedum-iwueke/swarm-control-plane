from unittest.mock import MagicMock

import pytest
from app.api.routes.execution_schedule_schemas import router
from app.schemas.execution_schedule_schema import ExecutionScheduleSchemaCreate
from app.services.execution_schedule_schema import (
    ExecutionScheduleSchemaConflict,
    digest,
    register_execution_schedule_schema,
)


def specification():
    return {"schema_version": "exec006-baseline-schedule-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "baseline-execution-scheduler",
        "version": "1.0.0",
        "producer": "bt.institutional.execution_scheduler.execution_schedule_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec006-pilot",
    }
    values.update(overrides)
    return ExecutionScheduleSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_execution_schedule_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_execution_schedule_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(ExecutionScheduleSchemaConflict, match="digest"):
        register_execution_schedule_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(ExecutionScheduleSchemaConflict, match="immutable"):
        register_execution_schedule_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/execution-schedule-schemas",
        "/v1/research/execution-schedule-schemas/{schema_id}",
    }
