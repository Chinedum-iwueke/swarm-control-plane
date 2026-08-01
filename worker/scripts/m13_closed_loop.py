from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from swarm_worker.executors.research_experiment import ResearchExperimentExecutor
from swarm_worker.policy import ResearchExperimentContract

WORKER = Path(__file__).resolve().parents[1]
SNAPSHOT = WORKER / "research-data/m13/binance-btcusdt-1h-2025.csv"
SNAPSHOT_MANIFEST = WORKER / "research-data/m13/manifest.json"
WORKSPACES = Path("/home/omenka/Projects/swarm-agent-workspaces")


def digest(document: Any) -> str:
    if isinstance(document, bytes):
        payload = document
    else:
        payload = json.dumps(
            document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    return hashlib.sha256(payload).hexdigest()


def call(
    client: httpx.Client, method: str, path: str, payload: dict | None = None
) -> Any:
    response = client.request(method, path, json=payload)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(
            f"{method} {path} returned HTTP {response.status_code}: {detail}"
        ) from exc
    return response.json()


def canonical_utc(value: str) -> str:
    """Match Pydantic's JSON representation before computing registry digests."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError("Registry timestamps must include a UTC offset.")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def api(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def role_state(path: Path) -> dict:
    if path.stat().st_mode & 0o077:
        raise RuntimeError("M13 role state must be mode 0600 or stricter.")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(admin: httpx.Client, roles: dict, commit: str) -> dict:
    snapshot_manifest = json.loads(SNAPSHOT_MANIFEST.read_text(encoding="utf-8"))
    actual_snapshot_digest = digest(SNAPSHOT.read_bytes())
    if actual_snapshot_digest != snapshot_manifest["content_sha256"]:
        raise RuntimeError("M13 snapshot no longer matches its manifest.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    question = "Does hourly BTC return sign predict the next hourly return after costs?"

    with api(roles["senior"]["token"]) as senior:
        governing = call(
            senior,
            "POST",
            "/v1/agent/research/knowledge/search",
            {
                "query": "signals before strategies negative results independent review",
                "limit": 5,
                "evidence_types": ["governing_requirement"],
            },
        )
        prior = call(
            senior,
            "POST",
            "/v1/agent/research/knowledge/search",
            {
                "query": "lagged return momentum prior experiment result",
                "limit": 5,
                "evidence_types": ["prior_result"],
            },
        )
        if not governing["passages"] or not prior["passages"]:
            raise RuntimeError(
                "M13 proposal retrieval lacks required evidence classes."
            )
        brief = call(
            senior,
            "POST",
            "/v1/agent/research/briefs",
            {
                "question": question,
                "summary": (
                    "Test one atomic lagged-return signal on a pinned historical BTC "
                    "snapshot; retain the result regardless of sign. "
                    f"Preparation run: {stamp}."
                ),
                "claims": [
                    {
                        "text": "The governing research process tests signals before constructing strategies and retains negative evidence.",
                        "evidence_class": "source_passage",
                        "citation_chunk_ids": [governing["passages"][0]["chunk_id"]],
                    },
                    {
                        "text": "The earlier M11 trial demonstrated digest-bound registration and independent result review on synthetic evidence.",
                        "evidence_class": "prior_result",
                        "citation_chunk_ids": [prior["passages"][0]["chunk_id"]],
                    },
                    {
                        "text": "Hourly BTC momentum may be absent after costs; rejection is an informative expected outcome.",
                        "evidence_class": "agent_inference",
                        "citation_chunk_ids": [],
                    },
                ],
            },
        )
        hypothesis_spec = {
            "research_question": question,
            "rationale": "A bounded real-data test moves the closed loop beyond synthetic validation without strategy optimization.",
            "mechanism": "Short-horizon information diffusion could make the preceding hourly return sign weakly persistent.",
            "prediction": "The sign signal has positive out-of-sample hourly Sharpe after five basis points per position change.",
            "universe": ["BINANCE:BTCUSDT"],
            "target": "next one-hour close-to-close return",
            "horizon": "one hour",
            "null_hypothesis": "Lagged hourly return sign has no positive out-of-sample predictive value after costs.",
            "failure_conditions": [
                "Out-of-sample annualized Sharpe is below 0.5.",
                "Double-cost annualized Sharpe is below 0.0.",
                "Out-of-sample drawdown exceeds 0.30.",
            ],
            "rival_explanations": [
                "Unconditional BTC drift or a narrow 2025 regime explains the result.",
                "Trading costs eliminate the gross effect.",
            ],
            "maximum_trials": 1,
        }
        hypothesis_digest = digest(hypothesis_spec)
        registered_hypotheses = call(admin, "GET", "/v1/research/hypotheses")
        hypothesis = next(
            (
                item
                for item in registered_hypotheses
                if item["record_digest"] == hypothesis_digest
            ),
            None,
        )
        hypothesis_reused = hypothesis is not None
        if hypothesis is None:
            hypothesis = call(
                senior,
                "POST",
                "/v1/agent/research/hypotheses",
                {
                    "hypothesis_key": f"M13-H1-{stamp}",
                    "trial_family": f"M13-BTC-HOURLY-MOMENTUM-{stamp}",
                    "specification": hypothesis_spec,
                    "record_digest": hypothesis_digest,
                },
            )

    if not hypothesis_reused:
        call(
            admin,
            "POST",
            f"/v1/research/hypothesis/{hypothesis['id']}/reviews",
            {
                "subject_digest": hypothesis["record_digest"],
                "review_kind": "approval",
                "verdict": "approved",
                "review": {
                    "summary": "Founder approved one prospective real-data trial."
                },
                "reviewer": "founder-operator",
            },
        )
    source_spec = {
        "title": "M13 Binance BTCUSDT canonical hourly snapshot",
        "source_type": "dataset",
        "version": snapshot_manifest["snapshot_key"],
        "content_sha256": actual_snapshot_digest,
        "provenance": (
            "Derived without network access from the existing VM1 canonical Binance "
            f"store; source digest {snapshot_manifest['source_sha256']}."
        ),
        "point_in_time": True,
        "observed_at": canonical_utc(snapshot_manifest["date_end"]),
    }
    source = call(
        admin,
        "POST",
        "/v1/research/sources",
        {
            "source_key": f"M13-BTC-SOURCE-{stamp}",
            "specification": source_spec,
            "record_digest": digest(source_spec),
            "registered_by": "research-registry",
        },
    )
    snapshot_spec = {
        "provider": "binance",
        "instrument": "BTCUSDT",
        "timeframe": "1h",
        "date_start": canonical_utc(snapshot_manifest["date_start"]),
        "date_end": canonical_utc(snapshot_manifest["date_end"]),
        "rows": snapshot_manifest["rows"],
        "format": "csv",
        "storage_uri": "worker/research-data/m13/binance-btcusdt-1h-2025.csv",
        "transformation": snapshot_manifest["transformation"],
        "point_in_time": True,
    }
    snapshot_document = {
        "snapshot_key": f"M13-BTC-1H-{stamp}",
        "source_id": source["id"],
        "specification": snapshot_spec,
        "content_digest": actual_snapshot_digest,
        "registered_by": "research-registry",
    }
    snapshot = call(
        admin,
        "POST",
        "/v1/research/data-snapshots",
        snapshot_document | {"record_digest": digest(snapshot_document)},
    )
    experiment_manifest = {
        "repository": "bulletproof_bt",
        "repository_commit": commit,
        "dataset_version": snapshot_manifest["snapshot_key"],
        "instrument_universe": ["BINANCE:BTCUSDT"],
        "timeframe": "1h",
        "date_start": "2025-01-01",
        "date_end": "2025-12-31",
        "sample_range": None,
        "features": ["one-hour lagged close-to-close return sign"],
        "target": "next one-hour close-to-close return",
        "model_or_rule": "long positive lagged return; short non-positive lagged return",
        "parameters": {"train_fraction": 0.65, "sealed_holdout_fraction": 0.35},
        "fees_bps": 5.0,
        "slippage_bps": 0.0,
        "delay_bars": 1,
        "validation_method": "locked 65/35 chronological split; doubled-cost and two-hour lag attacks",
        "success_criteria": [
            "OOS Sharpe >= 0.5",
            "OOS drawdown <= 0.30",
            "OOS trades >= 100",
            "double-cost Sharpe >= 0.0",
        ],
        "rejection_criteria": ["any locked success criterion fails"],
        "engine_version": f"bulletproof_bt:{commit}",
        "data_snapshot_digest": actual_snapshot_digest,
    }
    experiment_digest = digest(experiment_manifest)
    with api(roles["specification"]["token"]) as specification:
        experiment = call(
            specification,
            "POST",
            "/v1/agent/research/experiments",
            {
                "experiment_key": f"M13-EXP-1-{stamp}",
                "hypothesis_id": hypothesis["id"],
                "source_id": source["id"],
                "snapshot_id": snapshot["id"],
                "manifest": experiment_manifest,
                "manifest_digest": experiment_digest,
            },
        )
    call(
        admin,
        "POST",
        f"/v1/research/experiment/{experiment['id']}/reviews",
        {
            "subject_digest": experiment_digest,
            "review_kind": "approval",
            "verdict": "approved",
            "review": {
                "summary": "Founder approved the locked manifest digest before execution."
            },
            "reviewer": "founder-operator",
        },
    )
    task_contract = {
        "repository": "bulletproof_bt",
        "workflow": "research-experiment",
        "base_ref": commit,
        "program_id": "M13-CLOSED-FIVE",
        "hypothesis_id": hypothesis["hypothesis_key"],
        "hypothesis": "btc-hourly-lagged-return",
        "dataset": "binance-btcusdt-1h-2025",
        "dataset_digest": actual_snapshot_digest,
        "experiment_digest": experiment_digest,
        "trial_digest": None,
        "seed": 0,
        "observations": snapshot_manifest["rows"],
        "train_fraction": 0.65,
        "transaction_cost_bps": 5.0,
        "acceptance": {
            "minimum_out_of_sample_sharpe": 0.5,
            "maximum_out_of_sample_drawdown": 0.30,
            "minimum_out_of_sample_trades": 100,
            "minimum_cost_stress_sharpe": 0.0,
        },
    }
    task = call(
        admin,
        "POST",
        "/v1/tasks",
        {
            "task_number": f"M13-REAL-DATA-{stamp}",
            "project": "bulletproof_bt",
            "task_type": "research_experiment",
            "title": "M13 closed five-role BTC signal pilot",
            "objective": "Execute one founder-approved real-data signal experiment without live trading.",
            "priority": 70,
            "risk_level": 1,
            "created_by": "founder-operator",
            "input_contract": task_contract,
            "expected_outputs": [
                "research-evidence.json",
                "research-audit.json",
                "research-report.md",
            ],
            "acceptance_criteria": [
                "Complete positive or negative trial is reproduced, independently reviewed, and retained."
            ],
            "approval_policy": {"kind": "explicit", "risk": 1},
            "approval_required": True,
            "required_capabilities": [
                "git",
                "python",
                "backtesting",
                "research-execution",
            ],
            "allowed_machines": ["vm1-developer"],
            "max_attempts": 1,
        },
    )
    plan = {
        "run_id": task["task_number"],
        "task_id": task["id"],
        "code_commit": commit,
        "dataset_digest": actual_snapshot_digest,
        "engine_digest": digest(f"bulletproof_bt:{commit}:m13-signal-adapter".encode()),
    }
    trial_document = {
        "experiment_digest": experiment_digest,
        "trial_number": 1,
        "plan": plan,
        "executed_by": roles["execution"]["slug"],
    }
    trial = call(
        admin,
        "POST",
        f"/v1/research/experiments/{experiment['id']}/trials",
        {
            "experiment_digest": experiment_digest,
            "plan": plan,
            "record_digest": digest(trial_document),
            "executed_by": roles["execution"]["slug"],
        },
    )
    approvals = call(admin, "GET", "/v1/approvals?status=pending")
    approval = next(item for item in approvals if item["task_id"] == task["id"])
    return {
        "brief_id": brief["id"],
        "hypothesis_id": hypothesis["id"],
        "experiment_id": experiment["id"],
        "experiment_digest": experiment_digest,
        "source_id": source["id"],
        "snapshot_id": snapshot["id"],
        "snapshot_digest": actual_snapshot_digest,
        "trial_id": trial["id"],
        "trial_digest": trial["record_digest"],
        "task_id": task["id"],
        "task_number": task["task_number"],
        "approval_id": approval["id"],
        "approval_plan_digest": approval["plan_digest"],
        "repository_commit": commit,
    }


def execute(role_state_document: dict) -> dict:
    role = role_state_document["roles"]["execution"]
    environment = {
        "HOME": "/home/omenka",
        "PATH": f"{WORKER / '.venv/bin'}:/usr/bin:/bin",
        "VIRTUAL_ENV": str(WORKER / ".venv"),
        "SWARM_API_URL": os.environ["SWARM_API_URL"],
        "SWARM_AGENT_TOKEN": role["token"],
        "SWARM_AGENT_SLUG": role["slug"],
        "SWARM_MACHINE": "vm1-developer",
        "SWARM_ROLE_PACKAGE_MANIFEST": str(
            WORKER / "role-packages/m13-research-execution/manifest.yaml"
        ),
        "SWARM_WORKFLOW_DIRECTORY": str(WORKER / "workflows"),
    }
    completed = subprocess.run(
        [
            "/usr/sbin/runuser",
            "-u",
            "omenka",
            "--",
            "/usr/bin/env",
            "-i",
            *[f"{key}={value}" for key, value in environment.items()],
            str(WORKER / ".venv/bin/invariance-swarm-worker"),
            "once",
        ],
        cwd=WORKER,
        check=False,
        capture_output=True,
        text=True,
        timeout=1900,
    )
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


def finalize(admin: httpx.Client, roles: dict, state: dict) -> dict:
    task = call(admin, "GET", f"/v1/tasks/{state['task_id']}")["task"]
    if task["status"] != "succeeded" or task["attempt_count"] != 1:
        raise RuntimeError("M13 execution task has not succeeded exactly once.")
    candidates = list(WORKSPACES.glob(f"*-{state['task_id']}/attempt-1"))
    if len(candidates) != 1:
        raise RuntimeError("Exactly one retained M13 workspace is required.")
    workspace = candidates[0]
    evidence_path = workspace / "artifacts/research-evidence.json"
    audit_path = workspace / "artifacts/research-audit.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence["dataset"]["digest"] != state["snapshot_digest"]:
        raise RuntimeError("M13 evidence snapshot digest differs from the registry.")
    finding = evidence["finding"]
    result_document = {
        "summary": finding["reason"],
        "metrics": {
            **evidence["metrics"]["out_of_sample"],
            "cost_stress_sharpe": evidence["audit"]["cost_stress"]["annualized_sharpe"],
        },
        "robustness_status": "partial" if evidence["audit"]["passed"] else "failed",
        "rejection_reason": None
        if finding["verdict"] == "accepted"
        else finding["reason"],
        "evidence_artifacts": [
            digest(evidence_path.read_bytes()),
            digest(audit_path.read_bytes()),
        ],
        "output_artifact_digest": digest(evidence_path.read_bytes()),
        "started_at": task["started_at"],
        "ended_at": task["completed_at"],
    }
    result_payload = {
        "trial_digest": state["trial_digest"],
        "outcome": finding["verdict"],
        "result": result_document,
        "recorded_by": roles["execution"]["slug"],
    }
    result_record_digest = digest(result_payload)
    with api(roles["execution"]["token"]) as execution:
        result = call(
            execution,
            "POST",
            f"/v1/agent/research/trials/{state['trial_id']}/results",
            {
                key: value
                for key, value in result_payload.items()
                if key != "recorded_by"
            }
            | {"record_digest": result_record_digest},
        )

    contract = ResearchExperimentContract.model_validate(task["input_contract"])
    returns, _, _ = ResearchExperimentExecutor._load_dataset(contract)
    split = int(len(returns) * contract.train_fraction)
    reproduced = ResearchExperimentExecutor._evaluate(
        returns[split - 1 :],
        contract.transaction_cost_bps,
        lag=1,
        annualization=math.sqrt(365 * 24),
    )
    exact_reproduction = reproduced == evidence["metrics"]["out_of_sample"]
    with api(roles["statistical"]["token"]) as statistical:
        statistical_review = call(
            statistical,
            "POST",
            f"/v1/agent/research/results/{result['id']}/statistical-review",
            {
                "subject_digest": result["record_digest"],
                "verdict": "approved" if exact_reproduction else "rejected",
                "review": {
                    "exact_reproduction": exact_reproduction,
                    "trial_count": 1,
                    "selection_adjustment": "single prospective trial",
                    "confidence_grade": "limited-single-period",
                },
            },
        )
    benchmark = returns[split:]
    benchmark_sharpe = 0.0
    if len(benchmark) > 1 and statistics.stdev(benchmark):
        benchmark_sharpe = (
            math.sqrt(365 * 24)
            * statistics.fmean(benchmark)
            / statistics.stdev(benchmark)
        )
    attacks = {
        "cost_stress_sharpe": evidence["audit"]["cost_stress"]["annualized_sharpe"],
        "lag_stress_sharpe": evidence["audit"]["lag_stress"]["annualized_sharpe"],
        "buy_hold_sharpe": round(benchmark_sharpe, 8),
        "single_period_limitation": True,
        "production_eligible": False,
    }
    with api(roles["adversarial"]["token"]) as adversarial:
        adversarial_review = call(
            adversarial,
            "POST",
            f"/v1/agent/research/results/{result['id']}/adversarial-audit",
            {
                "subject_digest": result["record_digest"],
                "verdict": "approved" if exact_reproduction else "rejected",
                "review": attacks,
            },
        )
    decision = call(
        admin,
        "POST",
        f"/v1/research/results/{result['id']}/decisions",
        {
            "result_digest": result["record_digest"],
            "decision": "retain" if exact_reproduction else "reject",
            "rationale": "Retained as a reproducible non-live M13 result after separate statistical and adversarial reviews.",
            "decided_by": "founder-operator",
        },
    )
    lineage = call(
        admin, "GET", f"/v1/research/hypotheses/{state['hypothesis_id']}/lineage"
    )
    search = call(
        admin,
        "POST",
        "/v1/research/knowledge/search",
        {"query": "BTC hourly lagged return momentum", "limit": 5},
    )
    return {
        "task": {
            "id": task["id"],
            "status": task["status"],
            "attempt_count": task["attempt_count"],
        },
        "result": {
            "id": result["id"],
            "outcome": result["outcome"],
            "digest": result["record_digest"],
        },
        "statistical_review": statistical_review["id"],
        "adversarial_review": adversarial_review["id"],
        "decision": decision["id"],
        "exact_reproduction": exact_reproduction,
        "trial_family_count": lineage["trial_family_count"],
        "searchable_similar_hypotheses": len(search["similar_hypotheses"]),
        "workspace": str(workspace),
        "attacks": attacks,
    }


def write_state(path: Path, document: dict) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "execute", "finalize"))
    parser.add_argument("--roles", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--repository-commit")
    args = parser.parse_args()
    roles = role_state(args.roles)["roles"]
    if args.command == "execute":
        result = execute({"roles": roles})
    else:
        with api(os.environ["SWARM_ORCHESTRATOR_TOKEN"]) as admin:
            if args.command == "prepare":
                if not args.repository_commit or len(args.repository_commit) != 40:
                    raise RuntimeError("prepare requires a full repository commit")
                result = prepare(admin, roles, args.repository_commit)
                write_state(args.state, result)
            else:
                result = finalize(
                    admin, roles, json.loads(args.state.read_text(encoding="utf-8"))
                )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
