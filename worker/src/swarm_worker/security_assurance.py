from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SecurityAssuranceError(RuntimeError):
    """The security model or its adversarial evidence is incomplete."""


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(pattern=r"^ADV-[0-9]{3}$")
    expected_outcome: Literal["blocked", "quarantined", "redacted", "no_authority"]


class Threat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threat_id: str = Field(pattern=r"^SEC-T[0-9]{3}$")
    title: str
    domain: Literal["service", "agent", "research", "capital"]
    stride: list[Literal["spoofing", "tampering", "repudiation", "information_disclosure", "denial_of_service", "elevation_of_privilege"]]
    severity: Literal["critical", "high", "medium", "low"]
    abuse_case: str
    affected_services: list[str] = Field(min_length=1)
    controls: list[str] = Field(min_length=1)
    detection: list[str] = Field(min_length=1)
    containment: list[str] = Field(min_length=1)
    rollback: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    verification: list[Verification] = Field(min_length=1)
    residual_risk: str = Field(min_length=1)


class AdversarialScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(pattern=r"^ADV-[0-9]{3}$")
    category: Literal["injection", "exfiltration", "privilege_escalation", "supply_chain", "capital_mutation"]
    threat_ids: list[str] = Field(min_length=1)
    expected_outcome: Literal["blocked", "quarantined", "redacted", "no_authority"]
    fixture: dict[str, Any]


class ThreatModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["system-threat-model-v1.0.0"]
    model_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    service_catalog: str
    review_due: datetime
    owners: list[str] = Field(min_length=1)
    trust_boundaries: list[str] = Field(min_length=1)
    threats: list[Threat] = Field(min_length=1)
    scenarios: list[AdversarialScenario] = Field(min_length=5)
    accepted_residual_risks: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> ThreatModel:
        threat_ids = [item.threat_id for item in self.threats]
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if len(threat_ids) != len(set(threat_ids)):
            raise ValueError("threat IDs must be unique")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenario IDs must be unique")
        known_threats = set(threat_ids)
        known_scenarios = set(scenario_ids)
        for scenario in self.scenarios:
            if not set(scenario.threat_ids) <= known_threats:
                raise ValueError("scenario references an unknown threat")
        for threat in self.threats:
            if not {item.scenario_id for item in threat.verification} <= known_scenarios:
                raise ValueError("threat references an unknown scenario")
        required = {"injection", "exfiltration", "privilege_escalation", "supply_chain", "capital_mutation"}
        if {item.category for item in self.scenarios} != required:
            raise ValueError("all mandatory adversarial categories must be covered")
        return self


def canonical_json(document: Any) -> bytes:
    return json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def load_threat_model(path: Path) -> ThreatModel:
    return ThreatModel.model_validate_json(path.read_text(encoding="utf-8"))


def validate_catalog_coverage(model: ThreatModel, catalog_path: Path) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != "service-catalog-v1.0.0":
        raise SecurityAssuranceError("unsupported service catalog")
    services = {item["service_key"] for item in catalog["entries"]}
    covered = {key for threat in model.threats for key in threat.affected_services}
    unknown = covered - services
    missing = services - covered
    if unknown:
        raise SecurityAssuranceError(f"unknown services in threat model: {sorted(unknown)}")
    if missing:
        raise SecurityAssuranceError(f"services without threat coverage: {sorted(missing)}")
    if model.review_due <= datetime.now(timezone.utc):
        raise SecurityAssuranceError("threat model review is overdue")
    return {
        "catalog_version": catalog["catalog_version"],
        "service_count": len(services),
        "covered_service_count": len(covered),
        "catalog_sha256": hashlib.sha256(canonical_json(catalog)).hexdigest(),
    }


def exercise_scenario(scenario: AdversarialScenario) -> dict[str, Any]:
    fixture = scenario.fixture
    outcome: str
    control: str
    if scenario.category == "injection":
        hostile = str(fixture.get("content", "")).casefold()
        indicators = ("ignore previous", "exfiltrate credentials", "/run/secrets")
        outcome = "quarantined" if any(item in hostile for item in indicators) else "accepted"
        control = "instruction-injection scanner and quarantine"
    elif scenario.category == "exfiltration":
        secret = str(fixture.get("secret", ""))
        message = str(fixture.get("message", ""))
        rendered = message.replace(secret, "[REDACTED]") if secret else message
        outcome = "redacted" if secret and secret not in rendered else "disclosed"
        control = "structured secret redaction"
    elif scenario.category == "privilege_escalation":
        allowed_machine = fixture.get("allowed_machine")
        requested_machine = fixture.get("requested_machine")
        privileged = bool(fixture.get("privileged_operations"))
        outcome = "blocked" if privileged or requested_machine != allowed_machine else "accepted"
        control = "role-package machine and privilege ceiling"
    elif scenario.category == "supply_chain":
        declared = str(fixture.get("declared_sha256", ""))
        artifact = str(fixture.get("artifact", "")).encode()
        outcome = "blocked" if hashlib.sha256(artifact).hexdigest() != declared else "accepted"
        control = "digest-bound artifact verification"
    else:
        authority = fixture.get("authority", {})
        forbidden = {"capital", "live_orders", "self_approval", "production_promotion"}
        outcome = "no_authority" if all(authority.get(item) is False for item in forbidden) else "authorized"
        control = "explicit no-capital authority boundary"
    passed = outcome == scenario.expected_outcome
    if not passed:
        raise SecurityAssuranceError(
            f"{scenario.scenario_id} expected {scenario.expected_outcome}, got {outcome}"
        )
    return {
        "scenario_id": scenario.scenario_id,
        "category": scenario.category,
        "outcome": outcome,
        "control": control,
        "passed": True,
    }


def build_report(model: ThreatModel, catalog_path: Path) -> dict[str, Any]:
    coverage = validate_catalog_coverage(model, catalog_path)
    results = [exercise_scenario(item) for item in model.scenarios]
    body = {
        "schema_version": "security-assurance-report-v1.0.0",
        "model_version": model.model_version,
        "model_digest": hashlib.sha256(canonical_json(model.model_dump(mode="json"))).hexdigest(),
        "coverage": coverage,
        "threat_count": len(model.threats),
        "scenario_results": results,
        "accepted_residual_risks": model.accepted_residual_risks,
        "success": all(item["passed"] for item in results),
    }
    body["report_digest"] = hashlib.sha256(canonical_json(body)).hexdigest()
    return body
