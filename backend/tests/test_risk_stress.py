from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from app.api.routes.risk_stress import router
from app.schemas.risk_stress import RiskStressAssessmentCreate, RiskStressRequest
from app.services.research import record_digest
from app.services.risk_stress import (
    RiskStressConflict,
    build_dossier,
    register_assessment,
)
from pydantic import ValidationError

SCENARIOS = [
    "price_gap",
    "correlation_break",
    "liquidity_freeze",
    "model_failure",
    "prolonged_drawdown",
]


def request_value():
    return {
        "schema_version": "risk-stress-request-v1.0.0",
        "portfolio_candidate_key": "PORT001-PILOT",
        "candidate_digest": record_digest({"candidate": "PORT001"}),
        "portfolio_state_digest": record_digest({"state": "shadow"}),
        "bulletproof_run_digest": record_digest({"run": "BT004"}),
        "cost_model_digest": record_digest({"cost": "BT005"}),
        "scenario_pack_version": "v1.0.0",
        "scenario_pack_digest": record_digest({"pack": "RISK001"}),
        "evidence_age_seconds": 60,
        "drawdown": {
            "maximum_drawdown": 0.12,
            "maximum_duration_periods": 18,
            "recovery_duration_periods": 9,
            "underwater_path_digest": record_digest({"underwater": [0, -0.1, 0]}),
        },
        "tail": {
            "confidence_level": 0.95,
            "value_at_risk": 0.08,
            "expected_shortfall": 0.11,
            "expected_shortfall_upper_bound": 0.14,
            "method": "block_bootstrap",
            "sample_size": 2000,
            "receipt_digest": record_digest({"tail": "block"}),
        },
        "scenarios": [
            {
                "scenario": name,
                "version": "v1",
                "source_digest": record_digest({"scenario": name}),
                "loss_fraction": 0.08 + index * 0.01,
                "uncertainty_upper_bound": 0.10 + index * 0.01,
            }
            for index, name in enumerate(SCENARIOS)
        ],
        "reverse_stresses": [
            {
                "scenario": name,
                "breach_limit": 0.25,
                "last_safe_shock": 1.4 + index * 0.1,
                "first_breaching_shock": 1.5 + index * 0.1,
                "loss_at_breach": 0.251,
                "method": "bounded_bisection",
                "receipt_digest": record_digest({"reverse": name}),
            }
            for index, name in enumerate(SCENARIOS)
        ],
        "limits": {
            "maximum_drawdown": 0.2,
            "maximum_tail_loss": 0.2,
            "maximum_scenario_loss": 0.25,
            "maximum_evidence_age_seconds": 3600,
        },
        "validation_environment": "shadow",
        "allocation_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }


def payload(value=None):
    request = RiskStressRequest.model_validate(value or request_value())
    return RiskStressAssessmentCreate.model_validate(
        {
            "assessment_key": "RISK001-PILOT",
            "request": request,
            "request_digest": record_digest(request),
            "assessed_by": "risk001-pilot",
        }
    )


def test_complete_pack_is_admissible_without_authority():
    dossier, decision = build_dossier(payload())
    assert decision == "admissible"
    assert dossier["model_failure_included"] is True
    assert dossier["historical_variance_only"] is False
    assert dossier["capital_authority"] is False
    assert len(dossier["reverse_stress_thresholds"]) == 5


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_each_required_scenario_can_fail_closed(scenario):
    value = request_value()
    next(item for item in value["scenarios"] if item["scenario"] == scenario)[
        "uncertainty_upper_bound"
    ] = 0.3
    dossier, decision = build_dossier(payload(value))
    assert decision == "blocked"
    assert scenario in dossier["breached_scenarios"]
    assert "scenario_limit_breached" in dossier["failures"]


def test_stale_drawdown_and_tail_all_fail_closed():
    value = request_value()
    value["evidence_age_seconds"] = 7200
    value["drawdown"]["maximum_drawdown"] = 0.21
    value["tail"]["expected_shortfall_upper_bound"] = 0.22
    dossier, decision = build_dossier(payload(value))
    assert decision == "blocked"
    assert dossier["failures"] == [
        "stale_evidence",
        "drawdown_limit_breached",
        "tail_limit_breached",
    ]


def test_digest_tampering_is_rejected():
    value = payload().model_copy(update={"request_digest": "0" * 64})
    with pytest.raises(RiskStressConflict, match="digest"):
        build_dossier(value)


def test_missing_or_duplicate_scenario_is_invalid():
    value = request_value()
    value["scenarios"][-1] = deepcopy(value["scenarios"][0])
    with pytest.raises(ValidationError, match="five unique"):
        RiskStressRequest.model_validate(value)


def test_invalid_tail_and_reverse_stress_are_rejected():
    value = request_value()
    value["tail"]["expected_shortfall"] = 0.05
    with pytest.raises(ValidationError, match="expected shortfall"):
        RiskStressRequest.model_validate(value)
    value = request_value()
    value["reverse_stresses"][0]["loss_at_breach"] = 0.2
    with pytest.raises(ValidationError, match="reach its limit"):
        RiskStressRequest.model_validate(value)


def test_reverse_stress_limit_must_match_policy():
    value = request_value()
    value["reverse_stresses"][0]["breach_limit"] = 0.2
    with pytest.raises(RiskStressConflict, match="must match"):
        build_dossier(payload(value))


def test_registration_is_idempotent():
    db = MagicMock()
    db.scalar.return_value = None
    first = register_assessment(db, payload())
    db.scalar.return_value = first
    second = register_assessment(db, payload())
    assert second is first


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/risk-stress-assessments",
        "/v1/research/risk-stress-assessments/{assessment_id}",
    }
