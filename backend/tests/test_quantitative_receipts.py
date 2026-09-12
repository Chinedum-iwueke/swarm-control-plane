import hashlib
import json
from unittest.mock import MagicMock

import pytest
from app.api.routes.quantitative_receipts import router
from app.schemas.quantitative_receipt import QuantitativeReceiptCreate
from app.services.quantitative_receipt import (
    QuantitativeReceiptConflict,
    register_receipt,
)


def digest(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def receipt(
    milestone="ML-002", producer="bt.institutional.ml.causal_materialization_receipt"
):
    result = {"schema_version": "ml002-causal-materialization-v1.0.0", "rows": 10}
    core = {
        "schema_version": "bulletproof-producer-receipt-v1.0.0",
        "milestone": milestone,
        "producer": producer,
        "producer_version": "1.0.0",
        "source_commit": "a" * 64,
        "input_digest": "b" * 64,
        "dataset_digest": "c" * 64,
        "configuration_digest": "d" * 64,
        "artifact_digest": "e" * 64,
        "result_digest": digest(result),
        "result": result,
        "authority": {
            "allocation": False,
            "capital": False,
            "orders": False,
            "promotion": False,
        },
    }
    return {**core, "receipt_digest": digest(core)}


def payload(value=None):
    return QuantitativeReceiptCreate.model_validate(
        {"receipt": value or receipt(), "registered_by": "quantitative-bridge"}
    )


def test_registers_exact_authoritative_receipt():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_receipt(db, payload())
    assert record.milestone == "ML-002"
    assert record.receipt_digest == receipt()["receipt_digest"]
    assert record.receipt["authority"]["orders"] is False
    db.add.assert_called_once_with(record)


def test_registers_alpha001_only_from_bulletproof_admission_producer():
    value = receipt(
        milestone="ALPHA-001",
        producer="bt.institutional.alpha.real_data_admission_receipt",
    )
    value["result"] = {
        "schema_version": "alpha001-real-data-admission-v1.0.0",
        "admitted": True,
        "evidence_class": "live_exchange_history",
        "venue": "bybit",
        "instrument": "BTCUSDT",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.return_value = None
    record = register_receipt(db, payload(value))
    assert record.milestone == "ALPHA-001"
    assert record.receipt["authority"]["orders"] is False


def test_registration_is_idempotent():
    db = MagicMock()
    existing = object()
    db.scalar.return_value = existing
    assert register_receipt(db, payload()) is existing
    db.add.assert_not_called()


def test_rejects_wrong_milestone_producer():
    value = receipt(producer="bt.institutional.risk.stress_dossier_receipt")
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    with pytest.raises(QuantitativeReceiptConflict, match="not authoritative"):
        register_receipt(MagicMock(), payload(value))


def test_rejects_result_and_receipt_tampering():
    value = receipt()
    value["result"]["rows"] = 11
    with pytest.raises(QuantitativeReceiptConflict, match="Result digest"):
        register_receipt(MagicMock(), payload(value))
    value = receipt()
    value["receipt_digest"] = "f" * 64
    with pytest.raises(QuantitativeReceiptConflict, match="receipt digest"):
        register_receipt(MagicMock(), payload(value))


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/quantitative-receipts",
        "/v1/research/quantitative-receipts/{receipt_id}",
    }


def test_registers_port002_only_from_bulletproof_dependency_producer():
    value = receipt(
        milestone="PORT-002",
        producer="bt.institutional.portfolio.dependency_dossier_receipt",
    )
    value["result"] = {
        "schema_version": "port002-dependency-dossier-v1.0.0",
        "qualified": True,
        "claim": "dependency evidence only; no target weights or allocation authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.return_value = None
    record = register_receipt(db, payload(value))
    assert record.milestone == "PORT-002"
    assert record.producer == "bt.institutional.portfolio.dependency_dossier_receipt"
    assert record.receipt["authority"]["allocation"] is False


def test_port003_requires_active_registered_solver():
    value = receipt(
        milestone="PORT-003",
        producer="bt.institutional.construction.construction_dossier_receipt",
    )
    value["result"] = {
        "schema_version": "port003-construction-dossier-v1.0.0",
        "solver_digest": "9" * 64,
        "valid": True,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="solver is not active"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "PORT-003"


def test_exec001_requires_active_registered_event_schema():
    value = receipt(
        milestone="EXEC-001",
        producer="bt.institutional.execution.execution_journal_receipt",
    )
    value["result"] = {
        "schema_version": "exec001-canonical-journal-dossier-v1.0.0",
        "event_schema_digest": "8" * 64,
        "reconstructable": True,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="event schema is not active"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-001"


def test_exec002_requires_active_registered_model():
    value = receipt(
        milestone="EXEC-002",
        producer="bt.institutional.microstructure.microstructure_state_receipt",
    )
    value["result"] = {
        "schema_version": "exec002-microstructure-dossier-v1.0.0",
        "model_schema_digest": "7" * 64,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="model is not active"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    assert register_receipt(db, payload(value)).milestone == "EXEC-002"


def test_exec003_requires_active_registered_venue_identity():
    value = receipt(
        milestone="EXEC-003",
        producer="bt.institutional.venue.venue_identity_receipt",
    )
    value["result"] = {
        "schema_version": "exec003-venue-identity-v1.0.0",
        "mapping_schema_digest": "6" * 64,
        "qualified": True,
        "claim": "explicit comparison identity only; no order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="venue identity schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-003"
    assert record.receipt["authority"]["orders"] is False


def test_exec004_requires_active_registered_oms_schema():
    value = receipt(
        milestone="EXEC-004",
        producer="bt.institutional.oms.oms_reconciliation_receipt",
    )
    value["result"] = {
        "schema_version": "exec004-oms-reconciliation-v1.0.0",
        "oms_schema_digest": "5" * 64,
        "qualified": True,
        "claim": "deterministic OMS evidence only; no order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="OMS schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-004"
    assert record.receipt["authority"]["orders"] is False


def test_exec005_requires_active_registered_execution_calibration_schema():
    value = receipt(
        milestone="EXEC-005",
        producer="bt.institutional.execution_calibration.execution_calibration_receipt",
    )
    value["result"] = {
        "schema_version": "exec005-execution-calibration-v1.0.0",
        "calibration_schema_digest": "4" * 64,
        "qualified": True,
        "claim": "execution calibration evidence only; no order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="calibration schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-005"
    assert record.receipt["authority"]["orders"] is False


def test_port004_requires_active_registered_portfolio_capacity_schema():
    value = receipt(
        milestone="PORT-004",
        producer="bt.institutional.capacity.capacity_dossier_receipt",
    )
    value["result"] = {
        "schema_version": "port004-capacity-liquidity-v1.0.0",
        "capacity_schema_digest": "3" * 64,
        "qualified": True,
        "claim": "capacity evidence only; no capital or order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="capacity schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "PORT-004"
    assert record.receipt["authority"]["capital"] is False


def test_risk003_requires_active_registered_risk_budget_schema():
    value = receipt(
        milestone="RISK-003",
        producer="bt.institutional.risk_budget.dynamic_risk_budget_receipt",
    )
    value["result"] = {
        "schema_version": "risk003-dynamic-risk-budget-v1.0.0",
        "risk_budget_schema_digest": "2" * 64,
        "qualified": True,
        "claim": "bounded risk evidence only; no capital or order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="risk-budget schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "RISK-003"
    assert record.receipt["authority"]["capital"] is False
