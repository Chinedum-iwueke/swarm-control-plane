from unittest.mock import MagicMock

import pytest
from app.api.routes.risk_budget_schemas import router
from app.schemas.risk_budget_schema import RiskBudgetSchemaCreate
from app.services.risk_budget_schema import (
    RiskBudgetSchemaConflict,
    digest,
    register_risk_budget_schema,
)


def specification():
    return {"schema_version": "risk003-dynamic-risk-budget-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "dynamic-risk-budget-regime-scaling",
        "version": "1.0.0",
        "producer": "bt.institutional.risk_budget.dynamic_risk_budget_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "risk003-pilot",
    }
    values.update(overrides)
    return RiskBudgetSchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_risk_budget_schema(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_risk_budget_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(RiskBudgetSchemaConflict, match="digest"):
        register_risk_budget_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(RiskBudgetSchemaConflict, match="immutable"):
        register_risk_budget_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/risk-budget-schemas",
        "/v1/research/risk-budget-schemas/{schema_id}",
    }
