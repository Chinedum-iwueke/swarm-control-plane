from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.calibrations import router
from app.schemas.calibration import CalibrationAssessmentCreate
from app.services.calibration import (
    CalibrationConflict,
    build_assessment,
    register_assessment,
)
from app.services.research import record_digest
from pydantic import ValidationError

EVALUATION_ID = uuid4()
DOSSIER_ID = uuid4()


def specification(**updates):
    value = {
        "schema_version": "calibration-uncertainty-abstention-v1.0.0",
        "calibration_version": "ML004-PILOT-v1",
        "calibration_method": "held_out_platt",
        "reliability_bins": [
            {
                "lower_probability": lower,
                "upper_probability": upper,
                "observations": 100,
                "mean_probability": mean,
                "observed_frequency": observed,
            }
            for lower, upper, mean, observed in [
                (0.0, 0.2, 0.1, 0.11),
                (0.2, 0.4, 0.3, 0.29),
                (0.4, 0.6, 0.5, 0.51),
                (0.6, 0.8, 0.7, 0.69),
                (0.8, 1.0, 0.9, 0.91),
            ]
        ],
        "uncertainty": {
            "method": "split_conformal",
            "nominal_coverage": 0.9,
            "empirical_coverage": 0.91,
            "mean_interval_width": 0.18,
            "calibration_sample_digest": record_digest({"sample": "held-out"}),
        },
        "applicability_slices": [
            {
                "slice_key": regime,
                "observations": 200,
                "calibration_error": error,
                "shift_distance": shift,
                "supported": True,
            }
            for regime, error, shift in [("trend", 0.02, 0.4), ("range", 0.025, 0.5)]
        ],
        "explanation": {
            "method": "permutation_importance",
            "explanation_digest": record_digest({"explanation": "fixture"}),
            "fidelity_score": 0.94,
            "stability_score": 0.9,
            "causal_claims_prohibited": True,
        },
        "policy": {
            "maximum_expected_calibration_error": 0.05,
            "minimum_empirical_coverage": 0.88,
            "maximum_shift_distance": 2.0,
            "minimum_support": 50,
            "maximum_uncertainty": 0.35,
            "minimum_explanation_fidelity": 0.8,
        },
        "scenario_receipts": [
            {
                "scenario": scenario,
                "input_digest": record_digest({"scenario": scenario}),
                "probability": 0.62,
                "uncertainty": 0.15,
                "applicability": applicability,
                "support_count": support,
                "shift_distance": shift,
                "expected_calibration_error": error,
                "abstained": abstained,
                "abstention_reason": reason,
            }
            for scenario, applicability, support, shift, error, abstained, reason in [
                ("supported", "supported", 200, 0.5, 0.02, False, "none"),
                ("miscalibrated", "supported", 200, 0.5, 0.12, True, "miscalibrated"),
                (
                    "distribution_shift",
                    "out_of_support",
                    200,
                    3.0,
                    0.02,
                    True,
                    "distribution_shift",
                ),
                ("low_support", "supported", 10, 0.5, 0.02, True, "low_support"),
            ]
        ],
        "action_authority": False,
    }
    value.update(updates)
    return value


def payload(spec=None, **updates):
    spec = spec or specification()
    value = {
        "assessment_key": "ML004-PILOT",
        "evaluation_id": EVALUATION_ID,
        "dossier_id": DOSSIER_ID,
        "candidate_key": "regime-specialist",
        "specification": spec,
        "specification_digest": record_digest(spec),
        "assessed_by": "ml004-pilot",
    }
    value.update(updates)
    return CalibrationAssessmentCreate.model_validate(value)


def bound_records(qualified=True):
    evaluation = SimpleNamespace(
        id=EVALUATION_ID,
        scorecard_digest=record_digest({"scorecard": "ML003"}),
        scorecard={
            "qualified_candidate_keys": ["regime-specialist"] if qualified else []
        },
    )
    dossier = SimpleNamespace(
        id=DOSSIER_ID,
        record_digest=record_digest({"dossier": "RI004"}),
    )
    return evaluation, dossier


def test_qualified_assessment_recomputes_calibration_and_abstention():
    assessment, status = build_assessment(payload(), *bound_records())
    assert status == "qualified"
    assert assessment["expected_calibration_error"] == pytest.approx(0.01)
    assert assessment["scenario_receipts_valid"] is True
    assert assessment["mandatory_abstention"] is True
    assert assessment["capital_authority"] is False


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        (
            {
                "uncertainty": {
                    **specification()["uncertainty"],
                    "empirical_coverage": 0.7,
                }
            },
            "undercoverage",
        ),
        (
            {"explanation": {**specification()["explanation"], "fidelity_score": 0.4}},
            "misleading_explanation",
        ),
        (
            {
                "applicability_slices": [
                    {**specification()["applicability_slices"][0], "supported": False},
                    specification()["applicability_slices"][1],
                ]
            },
            "applicability_misclassified",
        ),
    ],
)
def test_failures_require_demotion(mutation, failure):
    assessment, status = build_assessment(
        payload(specification(**mutation)), *bound_records()
    )
    assert status == "demotion_required"
    assert failure in assessment["failures"]
    assert assessment["demotion_proposed"] is True


def test_miscalibrated_reliability_diagram_requires_demotion():
    spec = specification()
    spec["reliability_bins"] = [
        {
            **item,
            "observed_frequency": 0.9 if index == 0 else item["observed_frequency"],
        }
        for index, item in enumerate(spec["reliability_bins"])
    ]
    assessment, status = build_assessment(payload(spec), *bound_records())
    assert status == "demotion_required"
    assert "miscalibrated" in assessment["failures"]


def test_incorrect_abstention_receipt_requires_demotion():
    spec = specification()
    spec["scenario_receipts"][2]["abstained"] = False
    spec["scenario_receipts"][2]["abstention_reason"] = "none"
    assessment, status = build_assessment(payload(spec), *bound_records())
    assert status == "demotion_required"
    assert assessment["scenario_failures"] == ["distribution_shift"]


def test_unqualified_ml003_candidate_is_rejected():
    with pytest.raises(CalibrationConflict, match="not qualified"):
        build_assessment(payload(), *bound_records(qualified=False))


def test_reliability_bins_must_be_contiguous():
    spec = specification()
    spec["reliability_bins"][1]["lower_probability"] = 0.21
    with pytest.raises(ValidationError, match="contiguous"):
        payload(spec)


def test_registration_requires_both_bound_records():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(CalibrationConflict, match="required"):
        register_assessment(db, payload())


def test_routes_are_registered():
    paths = {route.path for route in router.routes}
    assert "/v1/research/model-calibrations" in paths
    assert "/v1/research/model-calibrations/{assessment_id}" in paths
