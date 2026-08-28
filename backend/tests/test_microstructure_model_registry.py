from unittest.mock import MagicMock

import pytest
from app.api.routes.microstructure_models import router
from app.schemas.microstructure_model import MicrostructureModelCreate
from app.services.microstructure_model import (
    MicrostructureModelConflict,
    digest,
    register_model,
)


def specification():
    return {"schema_version": "exec002-microstructure-model-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "typed-microstructure-state", "version": "1.0.0",
        "producer": "bt.institutional.microstructure.microstructure_state_receipt",
        "source_commit": "a" * 40, "specification_digest": digest(specification()),
        "specification": specification(), "status": "active", "registered_by": "exec002-bootstrap",
    }
    values.update(overrides)
    return MicrostructureModelCreate.model_validate(values)


def test_registers_and_replays_model_idempotently():
    db = MagicMock(); db.scalar.return_value = None
    record = register_model(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock(); replay.scalar.return_value = record
    assert register_model(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(MicrostructureModelConflict, match="digest"):
        register_model(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock(); db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(MicrostructureModelConflict, match="immutable"):
        register_model(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/microstructure-models", "/v1/research/microstructure-models/{model_id}"
    }
