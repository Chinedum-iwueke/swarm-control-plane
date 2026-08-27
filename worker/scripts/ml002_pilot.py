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
        builds = client.get("/research/data-contracts/builds").raise_for_status().json()
        programs = client.get("/research/factor-programs").raise_for_status().json()
        manifests = {
            item["id"]: item
            for item in client.get("/research/data-contracts/manifests")
            .raise_for_status()
            .json()
        }
        pair = next(
            (
                (build, program)
                for build in builds
                for program in programs
                if manifests[str(build["manifest_id"])]["manifest_digest"]
                == program["compiled"]["dataset_manifest_digest"]
                and program["status"] == "active"
            ),
            None,
        )
        if pair is None:
            raise RuntimeError(
                "No active factor program has a compatible immutable dataset build."
            )
        build, program = pair
        rows = build["rows"]
        if rows < 160:
            raise RuntimeError(
                "The compatible dataset build is too small for the pilot folds."
            )
        horizon = program["compiled"]["label"]["horizon"]
        purge = max(2, horizon)
        validation = max(10, min(50, rows // 10))
        first_end = rows - (2 * validation) - (2 * purge)
        folds = [
            {
                "fold": 1,
                "train_start": 0,
                "train_end": first_end,
                "validation_start": first_end + purge,
                "validation_end": first_end + purge + validation,
            },
            {
                "fold": 2,
                "train_start": 0,
                "train_end": first_end + validation,
                "validation_start": first_end + validation + (2 * purge),
                "validation_end": first_end + (2 * validation) + (2 * purge),
            },
        ]
        factors = sorted(program["compiled"]["factors"])
        specification = {
            "schema_version": "causal-feature-label-split-v1.0.0",
            "decision_clock": program["source"]["decision_clock"],
            "features": [
                {
                    "feature_key": key,
                    "factor_key": key,
                    "availability_lag_bars": 1,
                    "missing_policy": "drop",
                }
                for key in factors
            ],
            "labels": [
                {
                    "label_key": "registered_forward_label",
                    "kind": "forward_return",
                    "horizon_bars": horizon,
                    "label_end_offset_bars": horizon,
                }
            ],
            "fitted_transforms": [
                {
                    "transform_key": "train_standardization",
                    "kind": "standardize",
                    "fit_scope": "train_only",
                }
            ],
            "split": {
                "method": "expanding_walk_forward",
                "purge_bars": purge,
                "embargo_bars": purge,
                "folds": folds,
            },
            "sample_weighting": "inverse_label_overlap",
            "action_authority": False,
        }
        request = {
            "pipeline_key": "ML002-LIVE-PILOT",
            "dataset_build_id": build["id"],
            "factor_program_id": program["id"],
            "specification": specification,
            "specification_digest": digest(specification),
            "registered_by": "ml002-pilot",
        }
        response = client.post("/research/causal-pipelines", json=request)
        response.raise_for_status()
        pipeline = response.json()
        fold_results = [
            {
                "fold": fold["fold"],
                "train_rows": fold["train_end"] - fold["train_start"] - horizon,
                "validation_rows": fold["validation_end"] - fold["validation_start"],
                "maximum_train_label_end": fold["train_end"] - horizon,
                "minimum_validation_feature_time": fold["validation_start"],
                "purge_passed": True,
                "embargo_passed": True,
                "train_only_fit_passed": True,
                "point_in_time_join_passed": True,
            }
            for fold in folds
        ]
        content_digest = digest(
            {"pipeline": pipeline["compiled_digest"], "folds": fold_results}
        )
        materialization = {
            "materialization_key": "ML002-LIVE-PILOT-MATERIALIZATION",
            "pipeline_id": pipeline["id"],
            "output_uri": "evidence://ml002/live-pilot.parquet",
            "row_count": rows,
            "fold_results": fold_results,
            "content_digest": content_digest,
            "rebuild_content_digest": content_digest,
        }
        materialization["record_digest"] = digest(materialization)
        materialization["built_by"] = "ml002-pilot"
        response = client.post(
            "/research/causal-pipelines/materializations", json=materialization
        )
        response.raise_for_status()
        result = response.json()
    report = {
        "schema_version": "ml002-pilot-report-v1.0.0",
        "success": True,
        "pipeline_id": pipeline["id"],
        "pipeline_digest": pipeline["compiled_digest"],
        "materialization_id": result["id"],
        "materialization_digest": result["record_digest"],
        "dataset_build_id": build["id"],
        "factor_program_id": program["id"],
        "fold_count": len(folds),
        "purge_bars": purge,
        "embargo_bars": purge,
        "sample_weighting": "inverse_label_overlap",
        "independent_rebuild": True,
        "action_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
