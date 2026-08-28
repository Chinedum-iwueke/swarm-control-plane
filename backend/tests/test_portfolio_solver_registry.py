from unittest.mock import MagicMock

import pytest
from app.api.routes.portfolio_solvers import router
from app.schemas.portfolio_solver import PortfolioSolverCreate
from app.services.portfolio_solver import (
    PortfolioSolverConflict,
    digest,
    register_solver,
)


def specification():
    return {
        "name": "projected-gradient-robust-mean-variance",
        "version": "1.0.0",
        "objective": "uncertainty-penalized mean variance",
        "fallbacks": ["equal_weight", "risk_budget"],
        "deterministic": True,
    }


def payload(**overrides):
    document = specification()
    values = {
        "name": "projected-gradient-robust-mean-variance",
        "version": "1.0.0",
        "producer": "bt.institutional.construction.construction_dossier_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(document),
        "specification": document,
        "status": "active",
        "registered_by": "port003-bootstrap",
    }
    values.update(overrides)
    return PortfolioSolverCreate.model_validate(values)


def test_registers_and_idempotently_replays_solver():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_solver(db, payload())
    assert record.specification_digest == digest(specification())
    assert record.status == "active"
    db.add.assert_called_once_with(record)
    db = MagicMock()
    db.scalar.return_value = record
    assert register_solver(db, payload()) is record
    db.add.assert_not_called()


def test_rejects_digest_drift_and_immutable_version_reuse():
    with pytest.raises(PortfolioSolverConflict, match="digest"):
        register_solver(MagicMock(), payload(specification_digest="0" * 64))
    existing = MagicMock(specification_digest="1" * 64)
    db = MagicMock()
    db.scalar.return_value = existing
    with pytest.raises(PortfolioSolverConflict, match="immutable"):
        register_solver(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/portfolio-solvers",
        "/v1/research/portfolio-solvers/{solver_id}",
    }
