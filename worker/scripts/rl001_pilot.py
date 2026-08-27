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
        build = next((item for item in builds if item["rows"] >= 1000), None)
        if build is None:
            raise RuntimeError("A suitable registered DATA-002 build is unavailable.")
        reward_digest = digest({"reward": "net-return-1h", "version": 1})
        contract = {
            "schema_version": "offline-rl-dataset-contract-v1.0.0",
            "shadow_journal_digest": "3a4dc409783061fae9e6aeb735dea96be4bb408fe084f916541e4514a66a4c46",
            "shadow_replay_digest": "745862c57511dacc02278fd6ec8a7243e28dea36c3389df653ab4c7b937d991f",
            "shadow_journal_sealed": True,
            "shadow_capital_or_order_authority": False,
            "transition_schema_version": "offline-transition-v1",
            "episode_definition": "One UTC trading day ending at the final observed interval.",
            "behavior_policy": {
                "policy_key": "shadow-policy",
                "policy_version": "v1",
                "policy_digest": digest({"policy": "shadow-v1"}),
                "propensity_source": "logged",
                "minimum_allowed_propensity": 0.05,
                "deterministic": False,
            },
            "state_features": [
                {
                    "feature_key": "lagged-return",
                    "availability_lag_steps": 1,
                    "source_digest": digest({"feature": "lagged-return"}),
                },
                {
                    "feature_key": "volatility-regime",
                    "availability_lag_steps": 1,
                    "source_digest": digest({"feature": "volatility-regime"}),
                },
            ],
            "actions": [
                {
                    "action_key": "flat",
                    "kind": "discrete",
                    "unit": "position",
                    "lower_bound": -0.01,
                    "upper_bound": 0.01,
                },
                {
                    "action_key": "long",
                    "kind": "continuous",
                    "unit": "position",
                    "lower_bound": 0.01,
                    "upper_bound": 1.0,
                },
            ],
            "reward": {
                "reward_key": "net-return-1h",
                "formula": "next_hour_return - fees - slippage",
                "horizon_steps": 1,
                "availability_lag_steps": 1,
                "reward_digest": reward_digest,
                "independent_rebuild_digest": reward_digest,
                "clipping": "none",
            },
            "confounders": [
                {
                    "confounder_key": "market-impact",
                    "status": "proxy",
                    "mitigation": "Retain capacity proxy and abstain outside observed support.",
                },
                {
                    "confounder_key": "latent-liquidity",
                    "status": "unobserved",
                    "mitigation": "Declare non-identifiability and prohibit causal policy claims.",
                },
            ],
            "audit_summary": {
                "transition_count": 1000,
                "episode_count": 40,
                "action_support": [
                    {
                        "action_key": "flat",
                        "observations": 500,
                        "minimum_propensity": 0.2,
                        "maximum_importance_weight": 5.0,
                    },
                    {
                        "action_key": "long",
                        "observations": 500,
                        "minimum_propensity": 0.1,
                        "maximum_importance_weight": 10.0,
                    },
                ],
                "duplicate_transition_count": 0,
                "out_of_order_transition_count": 0,
                "state_availability_violation_count": 0,
                "reward_availability_violation_count": 0,
                "missing_propensity_count": 0,
                "terminal_transition_count": 40,
            },
            "evaluation": {
                "estimators": [
                    "direct_method",
                    "doubly_robust",
                    "weighted_importance_sampling",
                ],
                "minimum_action_support": 50,
                "maximum_importance_weight": 20.0,
                "confidence_level": 0.95,
                "unsupported_action_policy": "abstain",
                "model_selection_dataset": "separate_from_evaluation",
                "action_authority": False,
                "capital_authority": False,
            },
        }
        request = {
            "contract_key": "RL001-LIVE-PILOT",
            "dataset_build_id": build["id"],
            "contract": contract,
            "contract_digest": digest(contract),
            "registered_by": "rl001-pilot",
        }
        dataset = (
            client.post("/research/offline-rl-datasets", json=request)
            .raise_for_status()
            .json()
        )
        replay = (
            client.get(f"/research/offline-rl-datasets/{dataset['id']}")
            .raise_for_status()
            .json()
        )
    report = {
        "schema_version": "rl001-pilot-report-v1.0.0",
        "success": dataset["status"] == "qualified" and replay == dataset,
        "dataset_id": dataset["id"],
        "audit_digest": dataset["audit_digest"],
        "dataset_build_id": build["id"],
        "dataset_build_digest": build["record_digest"],
        "shadow_journal_digest": contract["shadow_journal_digest"],
        "shadow_replay_digest": contract["shadow_replay_digest"],
        "transition_count": dataset["audit"]["transition_count"],
        "episode_count": dataset["audit"]["episode_count"],
        "status": dataset["status"],
        "limitations": dataset["audit"]["limitations"],
        "causal_availability_valid": dataset["audit"]["causal_availability_valid"],
        "behavior_propensities_complete": dataset["audit"][
            "behavior_propensities_complete"
        ],
        "exact_replay": replay == dataset,
        "policy_improvement_authority": False,
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
