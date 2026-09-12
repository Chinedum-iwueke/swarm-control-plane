from unittest.mock import MagicMock

import pytest
from app.api.routes.portfolio_capacity_schemas import router
from app.schemas.portfolio_capacity_schema import PortfolioCapacitySchemaCreate
from app.services.portfolio_capacity_schema import (
    PortfolioCapacitySchemaConflict,
    digest,
    register_portfolio_capacity_schema,
)


def specification():
    return {"schema_version": "port004-capacity-liquidity-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "portfolio-turnover-cost-capacity-liquidity",
        "version": "1.0.0",
        "producer": "bt.institutional.capacity.capacity_dossier_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "port004-pilot",
    }
    values.update(overrides)
    return PortfolioCapacitySchemaCreate.model_validate(values)


def test_registers_and_replays_schema_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_portfolio_capacity_schema(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_portfolio_capacity_schema(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(PortfolioCapacitySchemaConflict, match="digest"):
        register_portfolio_capacity_schema(MagicMock(), payload(specification_digest="0" * 64))
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(PortfolioCapacitySchemaConflict, match="immutable"):
        register_portfolio_capacity_schema(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/portfolio-capacity-schemas",
        "/v1/research/portfolio-capacity-schemas/{schema_id}",
    }
