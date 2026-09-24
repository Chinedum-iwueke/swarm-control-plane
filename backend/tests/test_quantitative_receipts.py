import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.quantitative_receipts import router
from app.schemas.quantitative_receipt import QuantitativeReceiptCreate
from app.services.quantitative_receipt import (
    QuantitativeReceiptConflict,
    lake_inventory_summary,
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


@pytest.mark.parametrize("mutation", [None, "authority", "identity", "binding"])
def test_full_lake_inventory_is_accounting_not_admission(mutation):
    value = receipt(
        "DATA-002", "bt.institutional.lake_inventory.full_lake_inventory_receipt"
    )
    objects = [
        {
            "partition_id": "canonical/bybit/ETHUSDT/timeframe=1m/research_panel.parquet",
            "execution_eligible": False,
            "disposition": "cataloged_pending_quality",
            "market": "perp",
            "venue": "bybit",
            "instrument": "ETHUSDT",
            "content_digest": "a" * 64,
            "output_columns": ["ts", "close"],
            "row_count": 2,
        }
    ]
    value["result"] = {
        "schema_version": "data002-full-lake-inventory-v1.0.0",
        "objects": objects,
        "object_count": 1,
        "assets": [["perp", "bybit", "ETHUSDT"]],
        "dispositions": {"cataloged_pending_quality": 1},
        "claim_boundary": "Accounting only, not execution admission.",
    }
    value["input_digest"] = value["dataset_digest"] = digest(objects)
    if mutation == "authority":
        objects[0]["execution_eligible"] = True
    elif mutation == "identity":
        objects.append(dict(objects[0]))
        value["result"]["object_count"] = 2
    elif mutation == "binding":
        value["dataset_digest"] = "f" * 64
    value["result_digest"] = digest(value["result"])
    value["receipt_digest"] = digest(
        {key: item for key, item in value.items() if key != "receipt_digest"}
    )
    db = MagicMock()
    db.scalar.return_value = None
    if mutation:
        with pytest.raises(QuantitativeReceiptConflict):
            register_receipt(db, payload(value))
    else:
        assert register_receipt(db, payload(value)).milestone == "DATA-002"


def manifest_catalog_receipt():
    value = receipt(
        "DATA-002", "bt.institutional.lake_manifest.manifest_catalog_receipt"
    )
    manifests = {
        name: {
            "path": f"manifests/{name}.parquet",
            "content_digest": character * 64,
            "row_count": 1,
            "columns": ["market", "exchange", "symbol"],
        }
        for name, character in (
            ("coverage", "1"),
            ("fetch_state", "2"),
            ("instruments", "3"),
        )
    }
    availability = [
        {
            "market": "perp",
            "exchange": "bybit",
            "symbol": "ETHUSDT",
            "dataset": "ohlcv",
            "timeframe": "1m",
            "actual_rows": 600_000,
            "execution_eligible": False,
        }
    ]
    candidates = [
        {
            "market": "perp",
            "venue": "bybit",
            "instrument": "ETHUSDT",
            "timeframe": "1m",
            "actual_rows": 600_000,
            "execution_eligible": False,
        }
    ]
    value["result"] = {
        "schema_version": "data002-manifest-catalog-v1.0.0",
        "manifests": manifests,
        "manifest_count": 3,
        "availability": availability,
        "availability_record_count": 1,
        "assets": [["perp", "bybit", "ETHUSDT"]],
        "one_year_coverage_candidates": candidates,
        "venue_scope": ["binance", "bybit"],
        "memberships": {},
        "group_labels_are_optional_metadata": True,
        "execution_eligible": False,
        "claim_boundary": "Visibility only; selected panels require admission.",
    }
    value["input_digest"] = value["dataset_digest"] = digest(manifests)
    value["result_digest"] = digest(value["result"])
    value["receipt_digest"] = digest(
        {key: item for key, item in value.items() if key != "receipt_digest"}
    )
    return value


@pytest.mark.parametrize(
    "mutation", [None, "authority", "venue", "binding", "malformed_rows"]
)
def test_manifest_catalog_exposes_visibility_without_execution_admission(mutation):
    value = manifest_catalog_receipt()
    if mutation == "authority":
        value["result"]["availability"][0]["execution_eligible"] = True
    elif mutation == "venue":
        value["result"]["venue_scope"] = ["okx"]
    elif mutation == "binding":
        value["dataset_digest"] = "f" * 64
    elif mutation == "malformed_rows":
        value["result"]["availability"][0]["actual_rows"] = "many"
    value["result_digest"] = digest(value["result"])
    value["receipt_digest"] = digest(
        {key: item for key, item in value.items() if key != "receipt_digest"}
    )
    db = MagicMock()
    db.scalar.return_value = None
    if mutation:
        with pytest.raises(QuantitativeReceiptConflict):
            register_receipt(db, payload(value))
    else:
        assert register_receipt(db, payload(value)).milestone == "DATA-002"


def test_lake_summary_prefers_manifest_catalog_as_visibility_only():
    value = manifest_catalog_receipt()
    record = SimpleNamespace(
        id=uuid4(),
        receipt=value,
        receipt_digest=value["receipt_digest"],
        source_commit=value["source_commit"],
        producer=value["producer"],
    )
    db = MagicMock()
    db.scalar.return_value = record
    result = lake_inventory_summary(db)
    assert result["status"] == "manifest_catalog_visible_unadmitted"
    assert result["assets"] == [["perp", "bybit", "ETHUSDT"]]
    assert result["membership_records"] == []
    assert result["execution_authority"] is False


def test_manifest_catalog_accepts_bound_point_in_time_membership_metadata():
    value = manifest_catalog_receipt()
    value["result"]["schema_version"] = "data002-manifest-catalog-v1.1.0"
    value["result"]["manifests"]["stable_universe"] = {
        "path": "manifests/stable_universe.parquet",
        "content_digest": "4" * 64,
        "row_count": 1,
        "columns": ["market", "exchange", "symbol", "first_seen_ts"],
    }
    value["result"]["manifest_count"] = 4
    value["result"]["memberships"] = {
        "stable_universe": {
            "content_digest": "4" * 64,
            "row_count": 1,
            "columns": ["market", "exchange", "symbol", "first_seen_ts"],
            "classification": "optional_research_metadata",
        }
    }
    value["result"]["membership_records"] = [{
        "source_manifest": "stable_universe",
        "source_manifest_digest": "4" * 64,
        "membership_kind": "static",
        "group": "stable",
        "source_universe": "stable",
        "market": "perp",
        "venue": "bybit",
        "instrument": "ETHUSDT",
        "effective_from": "2025-01-01T00:00:00Z",
        "effective_to": "2025-01-01T00:00:00Z",
        "observation_count": 1,
        "available": True,
        "execution_eligible": False,
    }]
    value["result"]["membership_record_count"] = 1
    value["input_digest"] = value["dataset_digest"] = digest(
        value["result"]["manifests"]
    )
    value["result_digest"] = digest(value["result"])
    value["receipt_digest"] = digest(
        {key: item for key, item in value.items() if key != "receipt_digest"}
    )

    db = MagicMock()
    db.scalar.return_value = None
    assert register_receipt(db, payload(value)).milestone == "DATA-002"


def test_lake_summary_fails_closed_when_bound_receipt_digest_changes():
    value = manifest_catalog_receipt()
    record = SimpleNamespace(
        id=uuid4(),
        receipt=value,
        receipt_digest=value["receipt_digest"],
        source_commit=value["source_commit"],
        producer=value["producer"],
    )
    db = MagicMock()
    db.scalar.return_value = record
    result = lake_inventory_summary(db, receipt_id=record.id, receipt_digest="f" * 64)
    assert result == {
        "status": "bound_receipt_mismatch",
        "execution_authority": False,
    }


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
        "/v1/research/quantitative-receipts/lake-inventory",
    }


def test_exec011_requires_active_registered_telemetry_schema():
    value = receipt(
        milestone="EXEC-011",
        producer="bt.institutional.venue_telemetry.venue_telemetry_receipt",
    )
    value["result"] = {
        "schema_version": "exec011-venue-telemetry-v1.0.0",
        "telemetry_schema_digest": "7" * 64,
        "projection_digest": "8" * 64,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="execution-telemetry schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-011"


def test_risk005_requires_active_registered_realtime_risk_schema():
    value = receipt(
        milestone="RISK-005",
        producer="bt.institutional.realtime_risk.realtime_risk_decision_receipt",
    )
    value["result"] = {
        "schema_version": "risk005-realtime-risk-v1.0.0",
        "realtime_risk_schema_digest": "2" * 64,
        "allowed": False,
        "claim": "deterministic risk decision evidence only; no order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="real-time risk schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "RISK-005"
    assert record.receipt["authority"]["orders"] is False


def test_exec006_requires_active_registered_execution_schedule_schema():
    value = receipt(
        milestone="EXEC-006",
        producer="bt.institutional.execution_scheduler.execution_schedule_receipt",
    )
    value["result"] = {
        "schema_version": "exec006-baseline-schedule-v1.0.0",
        "execution_schedule_schema_digest": "3" * 64,
        "qualified": True,
        "risk005_required_per_child": True,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="execution-schedule schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-006"
    assert record.receipt["authority"]["orders"] is False


def test_exec007_requires_active_registered_execution_safety_schema():
    value = receipt(
        milestone="EXEC-007",
        producer="bt.institutional.runtime_safety.runtime_safety_receipt",
    )
    value["result"] = {
        "schema_version": "exec007-runtime-safety-v1.0.0",
        "runtime_safety_schema_digest": "4" * 64,
        "qualified": True,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="execution-safety schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-007"
    assert record.receipt["authority"]["orders"] is False


def test_exec008_requires_active_registered_adapter_certification_schema():
    value = receipt(
        milestone="EXEC-008",
        producer="bt.institutional.adapter_certification.adapter_certification_receipt",
    )
    value["result"] = {
        "schema_version": "exec008-adapter-certification-v1.0.0",
        "adapter_certification_schema_digest": "5" * 64,
        "status": "conformance_only",
        "qualified": False,
        "micro_live_eligible": False,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(
        QuantitativeReceiptConflict, match="adapter-certification schema"
    ):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-008"
    assert record.receipt["result"]["micro_live_eligible"] is False


def test_exec009_requires_active_registered_degradation_schema():
    value = receipt(
        milestone="EXEC-009",
        producer="bt.institutional.execution_degradation.execution_degradation_receipt",
    )
    value["result"] = {
        "schema_version": "exec009-execution-degradation-v1.0.0",
        "degradation_schema_digest": "7" * 64,
        "status": "restricted",
        "recommended_action": "route_restriction_review",
        "automatic_execution_change": False,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(
        QuantitativeReceiptConflict, match="execution-degradation schema"
    ):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "EXEC-009"
    assert record.receipt["authority"]["orders"] is False


def test_demo001_requires_active_registered_demo_certification_schema():
    value = receipt(
        milestone="DEMO-001",
        producer="bt.institutional.demo_certification.demo_certification_receipt",
    )
    value["result"] = {
        "schema_version": "demo001-production-like-venue-v1.0.0",
        "demo_certification_schema_digest": "6" * 64,
        "status": "blocked",
        "qualified": False,
        "micro_live_eligible": False,
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="demo-certification schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "DEMO-001"
    assert record.receipt["authority"]["orders"] is False


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


def test_shadow002_requires_active_registered_monitoring_schema():
    value = receipt(
        milestone="SHADOW-002",
        producer="bt.institutional.shadow_monitoring.shadow_monitoring_receipt",
    )
    value["result"] = {
        "schema_version": "shadow002-prospective-monitoring-v1.0.0",
        "shadow_monitoring_schema_digest": "1" * 64,
        "qualified_for_continued_shadow": True,
        "claim": "prospective monitoring evidence only; no capital or order authority",
    }
    value["result_digest"] = digest(value["result"])
    core = {key: item for key, item in value.items() if key != "receipt_digest"}
    value["receipt_digest"] = digest(core)
    db = MagicMock()
    db.scalar.side_effect = [None]
    with pytest.raises(QuantitativeReceiptConflict, match="monitoring schema"):
        register_receipt(db, payload(value))
    db = MagicMock()
    db.scalar.side_effect = [object(), None]
    record = register_receipt(db, payload(value))
    assert record.milestone == "SHADOW-002"
    assert record.receipt["authority"]["promotion"] is False
