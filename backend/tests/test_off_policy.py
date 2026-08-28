from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.off_policy import router
from app.schemas.off_policy import OffPolicyEvaluationCreate, OffPolicyProposal
from app.services.off_policy import (
    OffPolicyConflict,
    build_evaluation,
    register_evaluation,
)
from app.services.research import record_digest
from pydantic import ValidationError

DATASET_ID = uuid4()
AUDIT_ID = uuid4()
CALIBRATION_ID = uuid4()


def proposal(**updates):
    reward_digest = record_digest({"reward-model": "v1"})
    value = {
        "schema_version": "conservative-off-policy-proposal-v1.0.0",
        "target_policy_key": "conservative-regime-policy",
        "target_policy_version": "v1",
        "target_policy_digest": record_digest({"policy": "target-v1"}),
        "base_candidate_key": "regime-specialist",
        "estimators": [
            {
                "estimator": name,
                "point_estimate": point,
                "lower_confidence_bound": point - 0.01,
                "upper_confidence_bound": point + 0.01,
                "standard_error": 0.005,
                "effective_sample_size": 300,
                "maximum_importance_weight": weight,
                "estimate_digest": record_digest({"estimator": name}),
            }
            for name, point, weight in [
                ("direct_method", 0.04, 1.0),
                ("doubly_robust", 0.045, 8.0),
                ("weighted_importance_sampling", 0.038, 10.0),
            ]
        ],
        "stresses": [
            {
                "scenario": name,
                "lower_bound": lower,
                "affected_fraction": affected,
                "receipt_digest": record_digest({"stress": name}),
            }
            for name, lower, affected in [
                ("adversarial_reward", 0.018, 0.1),
                ("support_trimming", 0.02, 0.08),
                ("importance_weight_clipping", 0.021, 0.06),
                ("cost_expansion", 0.016, 1.0),
            ]
        ],
        "support": {
            "minimum_overlap": 0.2,
            "extrapolation_fraction": 0.03,
            "unsupported_actions": [],
        },
        "gate": {
            "minimum_conservative_value": 0.01,
            "minimum_effective_sample_size": 100,
            "minimum_overlap": 0.1,
            "maximum_extrapolation_fraction": 0.05,
            "maximum_estimator_spread": 0.02,
            "maximum_importance_weight": 20,
            "required_stress_scenarios": [
                "adversarial_reward",
                "support_trimming",
                "importance_weight_clipping",
                "cost_expansion",
            ],
        },
        "uncertainty_method": "block_bootstrap",
        "confidence_level": 0.95,
        "reward_model_digest": reward_digest,
        "independent_rebuild_digest": reward_digest,
        "validation_environment": "shadow",
        "deployment_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    value.update(updates)
    return value


def payload(value=None):
    validated = OffPolicyProposal.model_validate(value or proposal())
    return OffPolicyEvaluationCreate.model_validate(
        {
            "evaluation_key": "RL002-PILOT",
            "dataset_contract_id": DATASET_ID,
            "selection_audit_id": AUDIT_ID,
            "calibration_assessment_id": CALIBRATION_ID,
            "proposal": validated,
            "proposal_digest": record_digest(validated),
            "evaluated_by": "rl002-pilot",
        }
    )


def dependencies(
    dataset_status="qualified",
    audit_status="active",
    conclusion="clear",
    calibration_status="qualified",
):
    dataset = SimpleNamespace(
        id=DATASET_ID,
        status=dataset_status,
        audit_digest=record_digest({"dataset": "RL001"}),
        contract={
            "evaluation": {
                "estimators": [
                    "direct_method",
                    "doubly_robust",
                    "weighted_importance_sampling",
                ]
            }
        },
    )
    audit = SimpleNamespace(
        id=AUDIT_ID,
        status=audit_status,
        conclusion=conclusion,
        audit_digest=record_digest({"audit": "DISC007"}),
    )
    calibration = SimpleNamespace(
        id=CALIBRATION_ID,
        status=calibration_status,
        candidate_key="regime-specialist",
        assessment_digest=record_digest({"calibration": "ML004"}),
    )
    return dataset, audit, calibration


def test_conservative_proposal_is_shadow_eligible_without_authority():
    evaluation, decision = build_evaluation(payload(), *dependencies())
    assert decision == "shadow_eligible"
    assert evaluation["conservative_value"] == pytest.approx(0.016)
    assert evaluation["validation_environment"] == "shadow"
    assert evaluation["capital_authority"] is False


@pytest.mark.parametrize(
    ("mutate", "failure"),
    [
        (
            lambda value: value["stresses"][0].update(lower_bound=-0.01),
            "conservative_value_below_floor",
        ),
        (
            lambda value: value["estimators"][0].update(
                point_estimate=0.08,
                lower_confidence_bound=0.07,
                upper_confidence_bound=0.09,
            ),
            "estimator_disagreement",
        ),
        (
            lambda value: value["estimators"][1].update(effective_sample_size=50),
            "weak_effective_sample_size",
        ),
        (
            lambda value: value["estimators"][1].update(maximum_importance_weight=25),
            "unsafe_importance_weight",
        ),
        (lambda value: value["support"].update(minimum_overlap=0.05), "weak_overlap"),
        (
            lambda value: value["support"].update(extrapolation_fraction=0.2),
            "excess_extrapolation",
        ),
        (
            lambda value: value["support"].update(unsupported_actions=["short"]),
            "unsupported_actions",
        ),
    ],
)
def test_unsafe_proposals_are_rejected(mutate, failure):
    value = deepcopy(proposal())
    mutate(value)
    evaluation, decision = build_evaluation(payload(value), *dependencies())
    assert decision == "rejected"
    assert failure in evaluation["failures"]


def test_reward_model_rebuild_must_match():
    value = proposal()
    value["independent_rebuild_digest"] = record_digest({"wrong": True})
    with pytest.raises(ValidationError, match="reward model rebuild"):
        payload(value)


@pytest.mark.parametrize(
    "deps",
    [
        dependencies(dataset_status="quarantined"),
        dependencies(audit_status="superseded"),
        dependencies(conclusion="blocked"),
        dependencies(calibration_status="demotion_required"),
    ],
)
def test_unqualified_dependencies_fail_closed(deps):
    with pytest.raises(OffPolicyConflict):
        build_evaluation(payload(), *deps)


def test_candidate_must_match_calibration():
    dataset, audit, calibration = dependencies()
    calibration.candidate_key = "other-model"
    with pytest.raises(OffPolicyConflict, match="does not match"):
        build_evaluation(payload(), dataset, audit, calibration)


def test_registration_requires_all_dependencies():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(OffPolicyConflict, match="dependencies"):
        register_evaluation(db, payload())


def test_routes_are_registered():
    paths = {route.path for route in router.routes}
    assert "/v1/research/off-policy-evaluations" in paths
    assert "/v1/research/off-policy-evaluations/{evaluation_id}" in paths
