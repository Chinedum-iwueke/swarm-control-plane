from __future__ import annotations

import hashlib
import json
import math
import os
import random
import statistics
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from swarm_worker import __version__
from swarm_worker.executors.code_validation import (
    CodeValidationExecutor,
    HeartbeatCallback,
    RootExecutionError,
)
from swarm_worker.models import (
    StepExecutionResult,
    Task,
    WorkflowExecutionResult,
)
from swarm_worker.policy import ResearchExperimentContract
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace

_ANNUALIZATION = math.sqrt(252)


class ResearchExecutionError(RuntimeError):
    """The fixed experiment could not produce trustworthy evidence."""


class ResearchExperimentExecutor:
    def __init__(
        self,
        *,
        heartbeat_interval_seconds: float,
        validation_executor: CodeValidationExecutor | None = None,
        effective_uid: Callable[[], int] = os.geteuid,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._validation = validation_executor or CodeValidationExecutor(
            heartbeat_interval_seconds=heartbeat_interval_seconds
        )
        self._effective_uid = effective_uid
        self._clock = clock

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        if self._effective_uid() == 0:
            raise RootExecutionError("Research experiments must not run as root.")
        contract = ResearchExperimentContract.model_validate(task.input_contract)
        if workflow.name != "research-experiment":
            raise ResearchExecutionError("Research workflow identity is invalid.")

        started = self._clock()
        validation = await self._validation.execute(
            task=task,
            workflow=workflow,
            workspace=workspace,
            heartbeat=heartbeat,
        )
        if not validation.success:
            return validation

        steps = list(validation.steps)
        phase_names = (
            "generate-dataset",
            "execute-hypothesis",
            "audit-robustness",
            "report-finding",
        )
        total_steps = len(steps) + len(phase_names)
        await self._heartbeat(
            heartbeat, contract, steps, total_steps, started, phase_names[0]
        )
        returns, dataset_digest = self._generate_dataset(contract)
        steps.append(
            self._record_phase(
                workspace,
                phase_names[0],
                {
                    "dataset": contract.dataset,
                    "observations": len(returns),
                    "seed": contract.seed,
                    "dataset_digest": dataset_digest,
                },
            )
        )

        await self._heartbeat(
            heartbeat, contract, steps, total_steps, started, phase_names[1]
        )
        split = int(len(returns) * contract.train_fraction)
        train = self._evaluate(
            returns[:split], contract.transaction_cost_bps, lag=1
        )
        out_of_sample = self._evaluate(
            returns[split - 1 :],
            contract.transaction_cost_bps,
            lag=1,
        )
        steps.append(
            self._record_phase(
                workspace,
                phase_names[1],
                {"train": train, "out_of_sample": out_of_sample},
            )
        )

        await self._heartbeat(
            heartbeat, contract, steps, total_steps, started, phase_names[2]
        )
        audit = self._audit(contract, returns, split, out_of_sample)
        steps.append(self._record_phase(workspace, phase_names[2], audit))

        await self._heartbeat(
            heartbeat, contract, steps, total_steps, started, phase_names[3]
        )
        accepted = self._accepted(contract, out_of_sample, audit)
        evidence = self._evidence(
            contract,
            workspace,
            dataset_digest,
            train,
            out_of_sample,
            audit,
            accepted,
        )
        evidence_bytes = _canonical_json(evidence)
        evidence_digest = hashlib.sha256(evidence_bytes).hexdigest()
        artifacts = self._write_artifacts(
            workspace, evidence, evidence_bytes, evidence_digest
        )
        steps.append(
            self._record_phase(
                workspace,
                phase_names[3],
                {
                    "verdict": evidence["finding"]["verdict"],
                    "evidence_sha256": evidence_digest,
                    "artifacts": artifacts,
                },
            )
        )
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository=contract.repository,
            base_commit=workspace.plan.resolved_base_commit,
            task_attempt=task.attempt_count,
            total_duration_seconds=max(0.0, self._clock() - started),
            steps=steps,
            success=True,
            heartbeat_failures=validation.heartbeat_failures,
            worker_version=__version__,
            artifacts=artifacts,
            retryable=False,
            summary={
                "program_id": contract.program_id,
                "hypothesis_id": contract.hypothesis_id,
                "verdict": evidence["finding"]["verdict"],
                "production_eligible": False,
                "out_of_sample": out_of_sample,
                "audit_passed": audit["passed"],
                "evidence_sha256": evidence_digest,
            },
        )

    async def _heartbeat(
        self,
        heartbeat: HeartbeatCallback,
        contract: ResearchExperimentContract,
        steps: list[StepExecutionResult],
        total_steps: int,
        started: float,
        phase: str,
    ) -> None:
        await heartbeat(
            {
                "current_step": phase,
                "completed_step_count": len(steps),
                "total_step_count": total_steps,
                "elapsed_seconds": max(0.0, self._clock() - started),
                "program_id": contract.program_id,
            }
        )

    @staticmethod
    def _generate_dataset(
        contract: ResearchExperimentContract,
    ) -> tuple[list[float], str]:
        rng = random.Random(contract.seed)
        sign = 1.0
        values: list[float] = []
        for _ in range(contract.observations):
            if rng.random() > 0.72:
                sign *= -1
            magnitude = max(0.0001, abs(rng.gauss(0.004, 0.0015)))
            values.append(round(sign * magnitude, 12))
        digest = hashlib.sha256(_canonical_json(values)).hexdigest()
        return values, digest

    @staticmethod
    def _evaluate(
        returns: list[float], cost_bps: float, *, lag: int
    ) -> dict[str, float | int]:
        cost = cost_bps / 10_000
        strategy: list[float] = []
        previous_signal = 0.0
        trades = 0
        for index in range(lag, len(returns)):
            source = returns[index - lag]
            signal = 1.0 if source > 0 else -1.0
            changed = signal != previous_signal
            if changed:
                trades += 1
            strategy.append(signal * returns[index] - (cost if changed else 0.0))
            previous_signal = signal
        if len(strategy) < 2:
            raise ResearchExecutionError("Experiment produced insufficient returns.")
        mean = statistics.fmean(strategy)
        deviation = statistics.stdev(strategy)
        sharpe = _ANNUALIZATION * mean / deviation if deviation else 0.0
        equity = 1.0
        peak = 1.0
        maximum_drawdown = 0.0
        wins = 0
        for value in strategy:
            equity *= 1 + value
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak)
            wins += value > 0
        return {
            "observations": len(strategy),
            "trades": trades,
            "total_return": round(equity - 1, 8),
            "annualized_sharpe": round(sharpe, 8),
            "maximum_drawdown": round(maximum_drawdown, 8),
            "hit_rate": round(wins / len(strategy), 8),
        }

    def _audit(
        self,
        contract: ResearchExperimentContract,
        returns: list[float],
        split: int,
        out_of_sample: dict[str, float | int],
    ) -> dict[str, Any]:
        cost_stress = self._evaluate(
            returns[split - 1 :],
            contract.transaction_cost_bps * 2,
            lag=1,
        )
        lag_stress = self._evaluate(
            returns[split - 2 :],
            contract.transaction_cost_bps,
            lag=2,
        )
        checks = {
            "temporal_split_no_overlap": split > 1,
            "single_predeclared_hypothesis": True,
            "transaction_costs_applied": contract.transaction_cost_bps > 0,
            "minimum_sample_size": int(out_of_sample["observations"]) >= 100,
            "cost_stress_finite": math.isfinite(
                float(cost_stress["annualized_sharpe"])
            ),
            "lag_stress_finite": math.isfinite(
                float(lag_stress["annualized_sharpe"])
            ),
            "synthetic_data_disclosed": True,
            "production_promotion_blocked": True,
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "cost_stress": cost_stress,
            "lag_stress": lag_stress,
            "selection_count": 1,
            "limitations": [
                "Synthetic returns do not establish live-market validity.",
                "No parameter search or multiple-hypothesis selection was performed.",
                "The pilot does not model liquidity, latency, or market impact.",
            ],
        }

    @staticmethod
    def _accepted(
        contract: ResearchExperimentContract,
        out_of_sample: dict[str, float | int],
        audit: dict[str, Any],
    ) -> bool:
        acceptance = contract.acceptance
        return bool(
            audit["passed"]
            and float(out_of_sample["annualized_sharpe"])
            >= acceptance.minimum_out_of_sample_sharpe
            and float(out_of_sample["maximum_drawdown"])
            <= acceptance.maximum_out_of_sample_drawdown
            and int(out_of_sample["trades"])
            >= acceptance.minimum_out_of_sample_trades
            and float(audit["cost_stress"]["annualized_sharpe"])
            >= acceptance.minimum_cost_stress_sharpe
        )

    @staticmethod
    def _evidence(
        contract: ResearchExperimentContract,
        workspace: TaskWorkspace,
        dataset_digest: str,
        train: dict[str, float | int],
        out_of_sample: dict[str, float | int],
        audit: dict[str, Any],
        accepted: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "program_id": contract.program_id,
            "hypothesis_id": contract.hypothesis_id,
            "hypothesis": contract.hypothesis,
            "dataset": {
                "name": contract.dataset,
                "kind": "synthetic",
                "seed": contract.seed,
                "observations": contract.observations,
                "digest": dataset_digest,
            },
            "source": {
                "repository": contract.repository,
                "base_ref": contract.base_ref,
                "commit": workspace.plan.resolved_base_commit,
            },
            "parameters": {
                "train_fraction": contract.train_fraction,
                "transaction_cost_bps": contract.transaction_cost_bps,
            },
            "metrics": {"train": train, "out_of_sample": out_of_sample},
            "acceptance": contract.acceptance.model_dump(mode="json"),
            "audit": audit,
            "finding": {
                "verdict": "accepted" if accepted else "rejected",
                "production_eligible": False,
                "reason": (
                    "Synthetic out-of-sample thresholds and audit checks passed."
                    if accepted
                    else "One or more research thresholds or audit checks failed."
                ),
            },
        }

    @staticmethod
    def _record_phase(
        workspace: TaskWorkspace,
        name: str,
        output: dict[str, Any],
    ) -> StepExecutionResult:
        started_at = datetime.now(timezone.utc)
        started = time.monotonic()
        stdout = workspace.logs / f"{name}.stdout.log"
        stderr = workspace.logs / f"{name}.stderr.log"
        stdout.write_bytes(_canonical_json(output) + b"\n")
        stderr.write_text("", encoding="utf-8")
        stdout.chmod(0o600)
        stderr.chmod(0o600)
        ended_at = datetime.now(timezone.utc)
        return StepExecutionResult(
            name=name,
            success=True,
            return_code=0,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=max(0.0, time.monotonic() - started),
            stdout_log=stdout.relative_to(
                workspace.plan.attempt_directory
            ).as_posix(),
            stderr_log=stderr.relative_to(
                workspace.plan.attempt_directory
            ).as_posix(),
        )

    @staticmethod
    def _write_artifacts(
        workspace: TaskWorkspace,
        evidence: dict[str, Any],
        evidence_bytes: bytes,
        evidence_digest: str,
    ) -> list[str]:
        evidence_path = workspace.artifacts / "research-evidence.json"
        audit_path = workspace.artifacts / "research-audit.json"
        report_path = workspace.artifacts / "research-report.md"
        evidence_path.write_bytes(evidence_bytes)
        audit_path.write_bytes(_canonical_json(evidence["audit"]) + b"\n")
        metrics = evidence["metrics"]["out_of_sample"]
        report_path.write_text(
            "\n".join(
                [
                    f"# Research Finding: {evidence['hypothesis_id']}",
                    "",
                    f"**Verdict:** {evidence['finding']['verdict']}",
                    "**Production eligible:** no",
                    "",
                    "## Hypothesis",
                    "",
                    str(evidence["hypothesis"]),
                    "",
                    "## Out-of-sample evidence",
                    "",
                    f"- Annualized Sharpe: {metrics['annualized_sharpe']}",
                    f"- Maximum drawdown: {metrics['maximum_drawdown']}",
                    f"- Total return: {metrics['total_return']}",
                    f"- Trades: {metrics['trades']}",
                    "",
                    "## Audit",
                    "",
                    f"- Passed: {evidence['audit']['passed']}",
                    f"- Selection count: {evidence['audit']['selection_count']}",
                    "",
                    "## Provenance",
                    "",
                    f"- Dataset: {evidence['dataset']['name']} (synthetic)",
                    f"- Dataset digest: `{evidence['dataset']['digest']}`",
                    f"- Source commit: `{evidence['source']['commit']}`",
                    f"- Evidence digest: `{evidence_digest}`",
                    "",
                    "## Limitations",
                    "",
                    *[
                        f"- {limitation}"
                        for limitation in evidence["audit"]["limitations"]
                    ],
                    "",
                    "This result is research evidence, not a live-trading decision.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        for path in (evidence_path, audit_path, report_path):
            path.chmod(0o600)
        return [
            path.relative_to(workspace.plan.attempt_directory).as_posix()
            for path in (evidence_path, audit_path, report_path)
        ]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
