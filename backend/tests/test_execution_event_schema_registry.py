from unittest.mock import MagicMock

import pytest
from app.api.routes.execution_event_schemas import router
from app.schemas.execution_event_schema import ExecutionEventSchemaCreate
from app.services.execution_event_schema import (
    ExecutionEventSchemaConflict,
    digest,
    register_event_schema,
)


def specification():
    return {"schema_version": "canonical-execution-event-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "canonical-execution-event",
        "version": "1.0.0",
        "producer": "bt.institutional.execution.execution_journal_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec001-bootstrap",
    }
    values.update(overrides)
    return ExecutionEventSchemaCreate.model_validate(values)


def test_registers_and_idempotently_replays_event_schema():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_event_schema(db, payload())
    assert record.specification_digest == digest(specification())
    db.add.assert_called_once_with(record)
    replay_db = MagicMock()
    replay_db.scalar.return_value = record
    assert register_event_schema(replay_db, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(ExecutionEventSchemaConflict, match="digest"):
        register_event_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(ExecutionEventSchemaConflict, match="immutable"):
        register_event_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/execution-event-schemas",
        "/v1/research/execution-event-schemas/{schema_id}",
    }
