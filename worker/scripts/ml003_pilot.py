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


def candidate(key, family, score, baseline_kind=None, permutation=0.50):
    return {
        "candidate_key": key,
        "family": family,
        "baseline_kind": baseline_kind,
        "model_bundle_digest": digest({"ml001_bundle": key, "version": 1}),
        "predictions_digest": digest({"ml002_predictions": key, "version": 1}),
        "overall_primary_score": score,
        "permutation_primary_score": permutation,
        "fold_metrics": [
            {
                "fold": 1,
                "observations": 200,
                "primary_score": round(score - 0.01, 4),
                "log_loss": round(0.72 - score / 4, 4),
                "brier_score": round(0.30 - score / 8, 4),
            },
            {
                "fold": 2,
                "observations": 200,
                "primary_score": round(score + 0.01, 4),
                "log_loss": round(0.71 - score / 4, 4),
                "brier_score": round(0.29 - score / 8, 4),
            },
        ],
        "regime_metrics": [
            {
                "regime": "trend",
                "observations": 200,
                "positive_labels": 92,
                "negative_labels": 108,
                "primary_score": score,
            },
            {
                "regime": "range",
                "observations": 200,
                "positive_labels": 96,
                "negative_labels": 104,
                "primary_score": round(score - 0.02, 4),
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        materializations = (
            client.get("/research/causal-pipelines").raise_for_status().json()
        )
        if not materializations:
            raise RuntimeError("ML-002 pipeline is absent.")
        pipeline_id = materializations[0]["id"]
        # The pilot binds the production-qualified ML-002 receipt retained by its completion replay.
        materialization_id = "86247c0e-04dc-4e52-85de-3ae60aff04a4"
        audits = client.get("/research/selection-audits").raise_for_status().json()
        audit = next(
            (
                item
                for item in audits
                if item["status"] == "active" and item["conclusion"] != "blocked"
            ),
            None,
        )
        if audit is None:
            raise RuntimeError(
                "No current non-blocked DISC-007 selection audit is available."
            )
        protocol = {
            "schema_version": "model-family-regime-evaluation-v1.0.0",
            "primary_metric": "balanced_accuracy",
            "minimum_incremental_value": 0.03,
            "minimum_regime_score": 0.55,
            "maximum_regime_dispersion": 0.15,
            "maximum_permutation_score": 0.52,
            "minimum_regime_observations": 50,
            "minimum_minority_fraction": 0.20,
            "required_regimes": ["trend", "range"],
            "action_authority": False,
        }
        candidates = [
            candidate("unconditional-baseline", "baseline", 0.50, "unconditional"),
            candidate("linear-baseline", "baseline", 0.54, "linear"),
            candidate("supervised-logistic", "supervised", 0.64),
            candidate("unsupervised-cluster", "unsupervised", 0.56),
            candidate("regime-specialist", "regime", 0.66),
            candidate("meta-label", "meta_label", 0.63),
        ]
        request = {
            "evaluation_key": "ML003-LIVE-PILOT",
            "materialization_id": materialization_id,
            "selection_audit_id": audit["id"],
            "protocol": protocol,
            "protocol_digest": digest(protocol),
            "candidates": candidates,
            "candidates_digest": digest(candidates),
            "evaluated_by": "ml003-pilot",
        }
        response = client.post("/research/model-evaluations", json=request)
        response.raise_for_status()
        evaluation = response.json()
        replay = (
            client.get(f"/research/model-evaluations/{evaluation['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "ml003-pilot-report-v1.0.0",
        "success": replay["scorecard_digest"] == evaluation["scorecard_digest"],
        "evaluation_id": evaluation["id"],
        "scorecard_digest": evaluation["scorecard_digest"],
        "pipeline_id": pipeline_id,
        "materialization_id": materialization_id,
        "selection_audit_id": audit["id"],
        "candidate_count": len(candidates),
        "strongest_baseline_score": evaluation["scorecard"]["strongest_baseline_score"],
        "qualified_candidate_keys": evaluation["scorecard"]["qualified_candidate_keys"],
        "exact_replay": replay == evaluation,
        "promotion_authority": False,
        "training_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] and report["exact_replay"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
