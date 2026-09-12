from unittest.mock import MagicMock

import pytest
from app.api.routes.realtime_risk_schemas import router
from app.schemas.realtime_risk_schema import RealtimeRiskSchemaCreate
from app.services.realtime_risk_schema import (
    RealtimeRiskSchemaConflict,
    digest,
    register_realtime_risk_schema,
)


def specification():
    return {"schema_version": "risk005-realtime-risk-v1.0.0"}


def payload(**updates):
    values = {
        "name": "realtime-risk",
        "version": "1.0.0",
        "producer": "bt.institutional.realtime_risk.realtime_risk_decision_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "risk005-pilot",
    }
    values.update(updates)
    return RealtimeRiskSchemaCreate.model_validate(values)


def test_registers_idempotently_and_rejects_drift():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_realtime_risk_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_realtime_risk_schema(replay, payload()) is record
    with pytest.raises(RealtimeRiskSchemaConflict):
        register_realtime_risk_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    with pytest.raises(RealtimeRiskSchemaConflict, match="immutable"):
        register_realtime_risk_schema(
            replay, payload(source_commit="b" * 40)
        )


def test_routes_are_protected():
    assert router.dependencies
    assert len(router.routes) == 3
