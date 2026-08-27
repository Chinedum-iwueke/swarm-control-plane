#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        evaluations = (
            client.get("/research/model-evaluations").raise_for_status().json()
        )
        evaluation = next(
            (
                item
                for item in evaluations
                if "regime-specialist" in item["scorecard"]["qualified_candidate_keys"]
            ),
            None,
        )
        if evaluation is None:
            raise RuntimeError("A qualifying ML-003 evaluation is unavailable.")
        dossiers = client.get("/research/memory/dossiers").raise_for_status().json()
        if not dossiers:
            raise RuntimeError("An RI-004 evidence dossier is unavailable.")
        dossier = dossiers[0]
        specification = {
            "schema_version": "calibration-uncertainty-abstention-v1.0.0",
            "calibration_version": "ML004-LIVE-PILOT-v1",
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
                "calibration_sample_digest": digest({"sample": "held-out"}),
            },
            "applicability_slices": [
                {
                    "slice_key": regime,
                    "observations": 200,
                    "calibration_error": error,
                    "shift_distance": shift,
                    "supported": True,
                }
                for regime, error, shift in [
                    ("trend", 0.02, 0.4),
                    ("range", 0.025, 0.5),
                ]
            ],
            "explanation": {
                "method": "permutation_importance",
                "explanation_digest": digest({"explanation": "ML004 fixture"}),
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
                    "input_digest": digest({"scenario": scenario}),
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
                    (
                        "miscalibrated",
                        "supported",
                        200,
                        0.5,
                        0.12,
                        True,
                        "miscalibrated",
                    ),
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
        request = {
            "assessment_key": "ML004-LIVE-PILOT",
            "evaluation_id": evaluation["id"],
            "dossier_id": dossier["id"],
            "candidate_key": "regime-specialist",
            "specification": specification,
            "specification_digest": digest(specification),
            "assessed_by": "ml004-pilot",
        }
        assessment = (
            client.post("/research/model-calibrations", json=request)
            .raise_for_status()
            .json()
        )
        replay = (
            client.get(f"/research/model-calibrations/{assessment['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "ml004-pilot-report-v1.0.0",
        "success": assessment["status"] == "qualified" and replay == assessment,
        "assessment_id": assessment["id"],
        "assessment_digest": assessment["assessment_digest"],
        "evaluation_id": evaluation["id"],
        "dossier_id": dossier["id"],
        "candidate_key": assessment["candidate_key"],
        "status": assessment["status"],
        "expected_calibration_error": assessment["assessment"][
            "expected_calibration_error"
        ],
        "empirical_coverage": assessment["assessment"]["empirical_coverage"],
        "scenario_receipts_valid": assessment["assessment"]["scenario_receipts_valid"],
        "mandatory_abstention": assessment["assessment"]["mandatory_abstention"],
        "exact_replay": replay == assessment,
        "activation_authority": False,
        "promotion_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
