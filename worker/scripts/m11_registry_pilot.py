#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

STATE = Path("/home/omenka/.local/state/hermes/m11-pilot.json")
PROGRAM = Path(__file__).parents[1] / "research-programs/m8-pilot.yaml"
WORKSPACES = Path("/home/omenka/Projects/swarm-agent-workspaces")


def digest(document: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()


def request(
    client: httpx.Client, method: str, path: str, document: dict | None = None
) -> dict:
    response = client.request(method, path, json=document)
    response.raise_for_status()
    return response.json()


def source_spec() -> dict:
    # The deterministic generator digest is independently retained by the M8 pilot.
    return {
        "title": "M11 deterministic synthetic regime dataset",
        "source_type": "dataset",
        "version": "synthetic-regime-v1-seed-20260730",
        "content_sha256": "dbf9ec957b3987607b5abe9794a8f0ce33a0e06cc624ae10fcaec6b19446a46b",
        "provenance": (
            "Generated deterministically by the reviewed research executor from "
            "seed 20260730; not market data."
        ),
        "point_in_time": True,
        "observed_at": None,
    }


def hypothesis_spec() -> dict:
    return {
        "research_question": (
            "Does one-bar lagged return predict the next synthetic regime return "
            "after declared transaction costs?"
        ),
        "rationale": (
            "This bounded pilot tests whether a deliberately persistent synthetic "
            "regime is recovered out of sample."
        ),
        "mechanism": (
            "Regime persistence makes the preceding return sign informative about "
            "the next generated return."
        ),
        "prediction": (
            "A one-bar sign strategy retains positive out-of-sample Sharpe after "
            "five basis points of transaction cost."
        ),
        "universe": ["synthetic-regime-v1"],
        "target": "next synthetic return",
        "horizon": "one observation",
        "null_hypothesis": (
            "Lagged return has no positive out-of-sample predictive value after costs."
        ),
        "failure_conditions": [
            "Out-of-sample Sharpe is below 1.0.",
            "Out-of-sample drawdown exceeds 0.25.",
            "Fewer than 50 out-of-sample trades occur.",
            "Double-cost stress Sharpe is below 0.5.",
        ],
        "rival_explanations": [
            "The result is an artifact of the declared synthetic generator."
        ],
        "maximum_trials": 1,
    }


def experiment_manifest(commit: str) -> dict:
    return {
        "repository": "bulletproof_bt",
        "repository_commit": commit,
        "dataset_version": "synthetic-regime-v1-seed-20260730",
        "instrument_universe": ["synthetic-regime-v1"],
        "timeframe": "synthetic observation",
        "date_start": None,
        "date_end": None,
        "sample_range": "observations 0 through 1199",
        "features": ["one-bar lagged return sign"],
        "target": "next synthetic return",
        "model_or_rule": "long positive lagged return; short negative lagged return",
        "parameters": {"train_fraction": 0.65},
        "fees_bps": 5.0,
        "slippage_bps": 0.0,
        "delay_bars": 1,
        "validation_method": "fixed 65/35 chronological holdout and cost stress",
        "success_criteria": [
            "OOS Sharpe >= 1.0",
            "OOS drawdown <= 0.25",
            "OOS trades >= 50",
            "double-cost Sharpe >= 0.5",
        ],
        "rejection_criteria": ["any locked success criterion fails"],
        "engine_version": "invariance-swarm-worker-0.3.2",
    }


def prepare(client: httpx.Client) -> dict:
    commit = os.environ.get("M11_BULLETPROOF_COMMIT")
    if not commit or len(commit) != 40:
        raise RuntimeError("M11_BULLETPROOF_COMMIT must pin a 40-character commit.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    source_document = source_spec()
    source = request(
        client,
        "POST",
        "/v1/research/sources",
        {
            "source_key": f"M11-SYNTHETIC-SOURCE-{stamp}",
            "specification": source_document,
            "record_digest": digest(source_document),
            "registered_by": "research-registry",
        },
    )
    hypothesis_document = hypothesis_spec()
    hypothesis_digest = digest(hypothesis_document)
    hypothesis = request(
        client,
        "POST",
        "/v1/research/hypotheses",
        {
            "hypothesis_key": f"M11-H1-{stamp}",
            "trial_family": f"M11-SYNTHETIC-MOMENTUM-{stamp}",
            "specification": hypothesis_document,
            "record_digest": hypothesis_digest,
            "registered_by": "hypothesis-architect",
        },
    )
    request(
        client,
        "POST",
        f"/v1/research/hypothesis/{hypothesis['id']}/reviews",
        {
            "subject_digest": hypothesis_digest,
            "review_kind": "approval",
            "verdict": "approved",
            "review": {"summary": "Approved prospectively for exactly one trial."},
            "reviewer": "research-governor",
        },
    )
    manifest = experiment_manifest(commit)
    manifest_digest = digest(manifest)
    experiment = request(
        client,
        "POST",
        "/v1/research/experiments",
        {
            "experiment_key": f"M11-EXP-1-{stamp}",
            "hypothesis_id": hypothesis["id"],
            "source_id": source["id"],
            "manifest": manifest,
            "manifest_digest": manifest_digest,
            "registered_by": "experiment-specification-agent",
        },
    )
    request(
        client,
        "POST",
        f"/v1/research/experiment/{experiment['id']}/reviews",
        {
            "subject_digest": manifest_digest,
            "review_kind": "approval",
            "verdict": "approved",
            "review": {"summary": "Locked one-trial manifest approved."},
            "reviewer": "research-governor",
        },
    )
    program = yaml.safe_load(PROGRAM.read_text(encoding="utf-8"))
    contract = {
        key: value
        for key, value in program.items()
        if key not in {"schema_version", "project"}
    }
    contract["base_ref"] = commit
    task = request(
        client,
        "POST",
        "/v1/tasks",
        {
            "task_number": f"M11-RESEARCH-{stamp}",
            "project": "bulletproof_bt",
            "task_type": "research_experiment",
            "title": "M11 prospectively registered synthetic research trial",
            "objective": "Execute exactly one digest-approved M11 registry trial.",
            "priority": 65,
            "risk_level": 1,
            "created_by": "founder-operator",
            "input_contract": contract,
            "expected_outputs": [
                "research-evidence.json",
                "research-audit.json",
                "research-report.md",
            ],
            "acceptance_criteria": [
                "The locked manifest is executed once and retained regardless of outcome."
            ],
            "approval_policy": {"kind": "registry_gate", "risk": 1},
            "approval_required": True,
            "required_capabilities": ["git", "python", "backtesting", "research-audit"],
            "allowed_machines": ["vm1-developer"],
            "max_attempts": 1,
        },
    )
    plan = {
        "run_id": task["task_number"],
        "task_id": task["id"],
        "code_commit": commit,
        "dataset_digest": source_document["content_sha256"],
        "engine_digest": hashlib.sha256(
            b"invariance-swarm-worker-0.3.2:research-experiment"
        ).hexdigest(),
    }
    trial_document = {
        "experiment_digest": manifest_digest,
        "trial_number": 1,
        "plan": plan,
        "executed_by": "vm1-research-runner",
    }
    trial = request(
        client,
        "POST",
        f"/v1/research/experiments/{experiment['id']}/trials",
        {
            "experiment_digest": manifest_digest,
            "plan": plan,
            "record_digest": digest(trial_document),
            "executed_by": "vm1-research-runner",
        },
    )
    approvals = request(client, "GET", "/v1/approvals?status=pending")
    matching = [item for item in approvals if item["task_id"] == task["id"]]
    if len(matching) != 1:
        raise RuntimeError("Exactly one registry-gate approval is required.")
    request(
        client,
        "POST",
        f"/v1/approvals/{matching[0]['id']}/approve",
        {
            "actor": "research-registry",
            "reason": "Prospective trial reservation completed before execution.",
            "expires_in_seconds": 3600,
        },
    )
    return {
        "hypothesis_id": hypothesis["id"],
        "hypothesis_digest": hypothesis_digest,
        "experiment_id": experiment["id"],
        "manifest_digest": manifest_digest,
        "trial_id": trial["id"],
        "trial_digest": trial["record_digest"],
        "task_id": task["id"],
        "task_number": task["task_number"],
    }


def finalize(client: httpx.Client, state: dict) -> dict:
    task = request(client, "GET", f"/v1/tasks/{state['task_id']}")["task"]
    if task["status"] != "succeeded" or task["attempt_count"] != 1:
        raise RuntimeError("The prospectively registered task has not succeeded once.")
    candidates = list(WORKSPACES.glob(f"*-{state['task_id']}/attempt-1"))
    if len(candidates) != 1:
        raise RuntimeError("Exactly one retained task workspace is required.")
    workspace = candidates[0]
    evidence_path = workspace / "artifacts/research-evidence.json"
    audit_path = workspace / "artifacts/research-audit.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if (
        evidence["source"]["commit"] != os.environ.get("M11_BULLETPROOF_COMMIT")
        or evidence["dataset"]["digest"] != source_spec()["content_sha256"]
    ):
        raise RuntimeError("Execution does not match the locked commit and dataset.")
    finding = evidence["finding"]
    result_document = {
        "summary": finding["reason"],
        "metrics": {
            **evidence["metrics"]["out_of_sample"],
            "cost_stress_sharpe": evidence["audit"]["cost_stress"]["annualized_sharpe"],
        },
        "robustness_status": "partial",
        "rejection_reason": None
        if finding["verdict"] == "accepted"
        else finding["reason"],
        "evidence_artifacts": [
            hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        ],
        "output_artifact_digest": hashlib.sha256(
            evidence_path.read_bytes()
        ).hexdigest(),
        "started_at": task["started_at"],
        "ended_at": task["completed_at"],
    }
    result_payload = {
        "trial_digest": state["trial_digest"],
        "outcome": finding["verdict"],
        "result": result_document,
        "recorded_by": "vm1-research-runner",
    }
    result = request(
        client,
        "POST",
        f"/v1/research/trials/{state['trial_id']}/results",
        result_payload | {"record_digest": digest(result_payload)},
    )
    request(
        client,
        "POST",
        f"/v1/research/result/{result['id']}/reviews",
        {
            "subject_digest": result["record_digest"],
            "review_kind": "independent_review",
            "verdict": "approved",
            "review": {
                "summary": "Retained evidence and audit digests verified.",
                "production_eligible": False,
            },
            "reviewer": "statistical-reviewer",
        },
    )
    decision = request(
        client,
        "POST",
        f"/v1/research/results/{result['id']}/decisions",
        {
            "result_digest": result["record_digest"],
            "decision": "retain",
            "rationale": "Retain as systems evidence only; this synthetic result is not eligible for live trading.",
            "decided_by": "research-governor",
        },
    )
    lineage = request(
        client, "GET", f"/v1/research/hypotheses/{state['hypothesis_id']}/lineage"
    )
    return {
        **state,
        "result_id": result["id"],
        "decision_id": decision["id"],
        "trial_family_count": lineage["trial_family_count"],
        "lineage_counts": {
            name: len(lineage[name])
            for name in ("experiments", "trials", "results", "reviews", "decisions")
        },
        "production_eligible": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "finalize", "show"))
    args = parser.parse_args()
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    if args.action == "show":
        print(STATE.read_text(encoding="utf-8"))
        return 0
    with httpx.Client(
        base_url=api_url, headers={"Authorization": f"Bearer {token}"}, timeout=30
    ) as client:
        document = (
            prepare(client)
            if args.action == "prepare"
            else finalize(client, json.loads(STATE.read_text(encoding="utf-8")))
        )
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    STATE.chmod(0o600)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
