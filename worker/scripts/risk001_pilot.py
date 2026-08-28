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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/risk001/report.json"),
    )
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    names = [
        "price_gap",
        "correlation_break",
        "liquidity_freeze",
        "model_failure",
        "prolonged_drawdown",
    ]
    request = {
        "schema_version": "risk-stress-request-v1.0.0",
        "portfolio_candidate_key": "PORT001-LIVE-PILOT",
        "candidate_digest": digest({"candidate": "PORT001-live"}),
        "portfolio_state_digest": digest({"state": "shadow-20260828"}),
        "bulletproof_run_digest": digest({"run": "BT004-live"}),
        "cost_model_digest": digest({"cost": "BT005-live"}),
        "scenario_pack_version": "v1.0.0",
        "scenario_pack_digest": digest({"pack": "RISK001-live-v1"}),
        "evidence_age_seconds": 30,
        "drawdown": {
            "maximum_drawdown": 0.12,
            "maximum_duration_periods": 18,
            "recovery_duration_periods": 9,
            "underwater_path_digest": digest({"path": [0.0, -0.12, 0.0]}),
        },
        "tail": {
            "confidence_level": 0.95,
            "value_at_risk": 0.08,
            "expected_shortfall": 0.11,
            "expected_shortfall_upper_bound": 0.14,
            "method": "block_bootstrap",
            "sample_size": 2000,
            "receipt_digest": digest({"tail": "live"}),
        },
        "scenarios": [
            {
                "scenario": name,
                "version": "v1",
                "source_digest": digest({"scenario": name}),
                "loss_fraction": 0.08 + index * 0.01,
                "uncertainty_upper_bound": 0.10 + index * 0.01,
            }
            for index, name in enumerate(names)
        ],
        "reverse_stresses": [
            {
                "scenario": name,
                "breach_limit": 0.25,
                "last_safe_shock": 1.4 + index * 0.1,
                "first_breaching_shock": 1.5 + index * 0.1,
                "loss_at_breach": 0.251,
                "method": "bounded_bisection",
                "receipt_digest": digest({"reverse": name}),
            }
            for index, name in enumerate(names)
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
    payload = {
        "assessment_key": "RISK001-LIVE-PILOT",
        "request": request,
        "request_digest": digest(request),
        "assessed_by": "risk001-pilot",
    }
    with httpx.Client(
        base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=60.0
    ) as client:
        assessment = (
            client.post("/research/risk-stress-assessments", json=payload)
            .raise_for_status()
            .json()
        )
        replay = (
            client.get(f"/research/risk-stress-assessments/{assessment['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "risk001-pilot-report-v1.0.0",
        "success": assessment["decision"] == "admissible" and replay == assessment,
        "assessment_id": assessment["id"],
        "dossier_digest": assessment["dossier_digest"],
        "decision": assessment["decision"],
        "worst_scenario": assessment["dossier"]["worst_scenario"],
        "tail_loss_upper_bound": assessment["dossier"]["tail_loss_upper_bound"],
        "maximum_drawdown": assessment["dossier"]["maximum_drawdown"],
        "reverse_stress_thresholds": assessment["dossier"]["reverse_stress_thresholds"],
        "exact_replay": replay == assessment,
        "historical_variance_only": False,
        "model_failure_included": True,
        "allocation_authority": False,
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
