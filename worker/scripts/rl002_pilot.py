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
        datasets = client.get("/research/offline-rl-datasets").raise_for_status().json()
        dataset = next(
            (item for item in datasets if item["status"] == "qualified"), None
        )
        audits = client.get("/research/selection-audits").raise_for_status().json()
        audit = next(
            (
                item
                for item in audits
                if item["status"] == "active" and item["conclusion"] != "blocked"
            ),
            None,
        )
        calibrations = (
            client.get("/research/model-calibrations").raise_for_status().json()
        )
        calibration = next(
            (item for item in calibrations if item["status"] == "qualified"), None
        )
        if dataset is None or audit is None or calibration is None:
            raise RuntimeError(
                "RL-001, DISC-007 and ML-004 live dependencies are required."
            )
        reward_digest = digest({"reward-model": "v1"})
        proposal = {
            "schema_version": "conservative-off-policy-proposal-v1.0.0",
            "target_policy_key": "conservative-regime-policy",
            "target_policy_version": "v1",
            "target_policy_digest": digest({"policy": "target-v1"}),
            "base_candidate_key": calibration["candidate_key"],
            "estimators": [
                {
                    "estimator": name,
                    "point_estimate": point,
                    "lower_confidence_bound": point - 0.01,
                    "upper_confidence_bound": point + 0.01,
                    "standard_error": 0.005,
                    "effective_sample_size": 300,
                    "maximum_importance_weight": weight,
                    "estimate_digest": digest({"estimator": name}),
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
                    "receipt_digest": digest({"stress": name}),
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
        request = {
            "evaluation_key": "RL002-LIVE-PILOT",
            "dataset_contract_id": dataset["id"],
            "selection_audit_id": audit["id"],
            "calibration_assessment_id": calibration["id"],
            "proposal": proposal,
            "proposal_digest": digest(proposal),
            "evaluated_by": "rl002-pilot",
        }
        evaluation = (
            client.post("/research/off-policy-evaluations", json=request)
            .raise_for_status()
            .json()
        )
        replay = (
            client.get(f"/research/off-policy-evaluations/{evaluation['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "rl002-pilot-report-v1.0.0",
        "success": evaluation["decision"] == "shadow_eligible" and replay == evaluation,
        "evaluation_id": evaluation["id"],
        "evaluation_digest": evaluation["evaluation_digest"],
        "dataset_contract_id": dataset["id"],
        "selection_audit_id": audit["id"],
        "calibration_assessment_id": calibration["id"],
        "target_policy_digest": proposal["target_policy_digest"],
        "conservative_value": evaluation["evaluation"]["conservative_value"],
        "estimator_spread": evaluation["evaluation"]["estimator_spread"],
        "decision": evaluation["decision"],
        "failures": evaluation["evaluation"]["failures"],
        "validation_environment": "shadow",
        "exact_replay": replay == evaluation,
        "causal_policy_claim_authority": False,
        "deployment_authority": False,
        "order_authority": False,
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
