from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from swarm_worker.security_assurance import (
    SecurityAssuranceError,
    ThreatModel,
    build_report,
    load_threat_model,
    validate_catalog_coverage,
)

ROOT = Path(__file__).parents[2]
MODEL_PATH = ROOT / "worker/security/hermes-system-threat-model-v1.json"
CATALOG_PATH = ROOT / "worker/service-catalog/hermes-platform-v1.json"


def test_all_catalog_services_and_required_attack_classes_are_covered() -> None:
    model = load_threat_model(MODEL_PATH)
    coverage = validate_catalog_coverage(model, CATALOG_PATH)

    assert coverage["service_count"] == coverage["covered_service_count"] == 12
    assert {item.category for item in model.scenarios} == {
        "injection",
        "exfiltration",
        "privilege_escalation",
        "supply_chain",
        "capital_mutation",
    }
    assert all(item.rollback and item.detection and item.containment for item in model.threats)


def test_report_is_digest_bound_redacted_and_fail_closed() -> None:
    report = build_report(load_threat_model(MODEL_PATH), CATALOG_PATH)
    serialized = json.dumps(report, sort_keys=True)

    assert report["success"] is True
    assert len(report["scenario_results"]) == 5
    assert all(item["passed"] for item in report["scenario_results"])
    assert "SEC001_SYNTHETIC_SECRET_DO_NOT_LOG" not in serialized
    assert len(report["model_digest"]) == 64
    assert len(report["report_digest"]) == 64


def test_missing_service_coverage_is_rejected() -> None:
    document = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    for threat in document["threats"]:
        threat["affected_services"] = [
            item for item in threat["affected_services"] if item != "mission-control"
        ]
    model = ThreatModel.model_validate(document)

    with pytest.raises(SecurityAssuranceError, match="mission-control"):
        validate_catalog_coverage(model, CATALOG_PATH)


def test_tampered_hostile_fixture_cannot_be_reported_as_passing() -> None:
    document = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(document)
    supply_chain = next(
        item for item in mutated["scenarios"] if item["category"] == "supply_chain"
    )
    supply_chain["fixture"]["declared_sha256"] = hashlib.sha256(
        supply_chain["fixture"]["artifact"].encode()
    ).hexdigest()

    with pytest.raises(SecurityAssuranceError, match="ADV-004"):
        build_report(ThreatModel.model_validate(mutated), CATALOG_PATH)


def test_capital_authority_mutation_is_not_silently_accepted() -> None:
    document = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    capital = next(
        item for item in document["scenarios"] if item["category"] == "capital_mutation"
    )
    capital["fixture"]["authority"]["live_orders"] = True

    with pytest.raises(SecurityAssuranceError, match="ADV-005"):
        build_report(ThreatModel.model_validate(document), CATALOG_PATH)
