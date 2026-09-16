from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from swarm_worker import __version__
from swarm_worker.executors.code_validation import HeartbeatCallback, RootExecutionError
from swarm_worker.models import StepExecutionResult, Task, WorkflowExecutionResult
from swarm_worker.policy import AlphaResearchExecutionContract
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace


class AlphaResearchExecutionError(RuntimeError):
    """The native Bulletproof execution boundary failed closed."""


def _qualification_handoff(qualification: dict) -> dict:
    """Keep the task summary bounded while preserving execution inputs."""
    artifact_bundle = qualification.get("artifact_bundle")
    if not isinstance(artifact_bundle, dict):
        return qualification
    required_artifacts = ("engine_hypothesis_yaml", "strategy_spec")
    if any(name not in artifact_bundle for name in required_artifacts):
        raise AlphaResearchExecutionError(
            "Qualified strategy is missing a required execution artifact."
        )
    retained = {
        key: qualification[key]
        for key in (
            "schema_version",
            "qualified",
            "card",
            "card_digest",
            "dataset",
            "parameter_grid",
            "review",
            "tier",
            "variant_count",
            "window",
            "authority",
        )
        if key in qualification
    }
    retained["artifact_bundle"] = {
        name: artifact_bundle[name] for name in required_artifacts
    }
    return retained


class AlphaResearchExecutor:
    def __init__(
        self,
        *,
        heartbeat_interval_seconds: float,
        effective_uid=os.geteuid,
        python_path: Path = Path(
            "/home/omenka/Projects/bulletproof_bt/.venv/bin/python"
        ),
        capacity_database: Path | None = None,
    ) -> None:
        self._heartbeat_interval = max(5.0, heartbeat_interval_seconds)
        self._effective_uid = effective_uid
        self._python = python_path
        configured = os.environ.get("SWARM_BULLETPROOF_CAPACITY_DB")
        self._capacity_database = capacity_database or (
            Path(configured) if configured else None
        )

    def capacity_progress(self) -> dict:
        if self._capacity_database is None:
            return {}
        try:
            path = self._capacity_database.parent / "alpha-capacity-state.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            observed = datetime.fromisoformat(data["updated_at"])
            age = (datetime.now(UTC) - observed).total_seconds()
            return {
                "telemetry_current": 0 <= age <= 60,
                "worker_slots": data.get("worker_slots", {}),
                "jobs": [
                    {
                        "queue_id": item.get("queue_id"),
                        "status": item.get("status"),
                        "estimated_workers": item.get("estimated_workers"),
                    }
                    for item in data.get("jobs", [])[:16]
                ],
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {"telemetry_current": False}

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        if self._effective_uid() == 0:
            raise RootExecutionError("Alpha research must not run as root.")
        contract = AlphaResearchExecutionContract.model_validate(task.input_contract)
        if workflow.name != "alpha-research-execution" or workflow.steps:
            raise AlphaResearchExecutionError("Alpha workflow identity is invalid.")
        if not self._python.is_file():
            raise AlphaResearchExecutionError("Bulletproof virtualenv is unavailable.")
        dataset = Path(contract.dataset_path)
        resolved_dataset = dataset.resolve(strict=True)
        resolved_root = Path(
            "/home/omenka/Projects/bulletproof_bt/research_data"
        ).resolve(strict=True)
        if (
            not dataset.is_file()
            or dataset.is_symlink()
            or not resolved_dataset.is_relative_to(resolved_root)
        ):
            raise AlphaResearchExecutionError(
                "Admitted dataset is missing or symlinked."
            )
        for binding in contract.dataset_bindings:
            bound_path = Path(binding.dataset_path)
            resolved_path = bound_path.resolve(strict=True)
            if (
                not bound_path.is_file()
                or bound_path.is_symlink()
                or not resolved_path.is_relative_to(resolved_root)
            ):
                raise AlphaResearchExecutionError(
                    "An admitted basket panel is missing or symlinked."
                )

        started_at = datetime.now(UTC)
        started = time.monotonic()
        assignment = workspace.artifacts / "alpha-assignment.json"
        receipt = workspace.artifacts / "alpha-research-receipt.json"
        stdout_path = workspace.logs / "native-alpha.stdout.log"
        stderr_path = workspace.logs / "native-alpha.stderr.log"
        assignment.write_text(
            json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        command = (
            str(self._python),
            str(workspace.repository / "scripts/run_alpha_research_assignment.py"),
            "--assignment",
            str(assignment),
            "--repository-root",
            str(workspace.repository),
            "--output",
            str(workspace.artifacts / "native-run"),
            "--receipt",
            str(receipt),
        )
        if self._capacity_database is not None and contract.stage == "execute":
            if not 1 <= contract.max_variants <= 8:
                raise AlphaResearchExecutionError(
                    "Capacity-governed grids require 1-8 variants."
                )
            command = (
                str(self._python),
                str(
                    workspace.repository / "scripts/queue_alpha_capacity_assignment.py"
                ),
                "--db",
                str(self._capacity_database),
                *command[2:],
            )
        env = {
            "PATH": str(self._python.parent) + ":/usr/bin:/bin",
            "HOME": str(workspace.plan.attempt_directory),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(workspace.repository / "src"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=workspace.repository,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
            )
            while True:
                try:
                    return_code = await asyncio.wait_for(
                        process.wait(), timeout=self._heartbeat_interval
                    )
                    break
                except TimeoutError:
                    elapsed = time.monotonic() - started
                    if elapsed >= workflow.timeout_seconds:
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=30)
                        except TimeoutError:
                            process.kill()
                            await process.wait()
                        return_code = 124
                        break
                    try:
                        await heartbeat(
                            {
                                "phase": "native_bulletproof_execution",
                                "elapsed_seconds": round(elapsed, 3),
                                "campaign_id": contract.campaign_id,
                                "question_digest": contract.question_digest,
                                "capacity_governed": self._capacity_database is not None
                                and contract.stage == "execute",
                                "capacity": self.capacity_progress(),
                            }
                        )
                    except asyncio.CancelledError:
                        process.terminate()
                        await process.wait()
                        raise

        ended_at = datetime.now(UTC)
        step = StepExecutionResult(
            name="native-bulletproof-alpha",
            success=return_code == 0,
            return_code=return_code,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=max(0.0, time.monotonic() - started),
            stdout_log=stdout_path.relative_to(
                workspace.plan.attempt_directory
            ).as_posix(),
            stderr_log=stderr_path.relative_to(
                workspace.plan.attempt_directory
            ).as_posix(),
        )
        if return_code != 0 or not receipt.is_file():
            return WorkflowExecutionResult(
                workflow=workflow.name,
                repository=contract.repository,
                base_commit=workspace.plan.resolved_base_commit,
                task_attempt=task.attempt_count,
                total_duration_seconds=step.duration_seconds,
                steps=[step],
                success=False,
                termination_reason=(
                    "workflow_timeout"
                    if return_code == 124
                    else "native_bulletproof_failed"
                ),
                worker_version=__version__,
                retryable=True,
            )
        document = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            document.get("stage") != contract.stage
            or document.get("campaign_digest") != contract.campaign_digest
            or document.get("question_digest") != contract.question_digest
            or document.get("dataset_digest") != contract.dataset_digest
            or document.get("source_commit") != workspace.plan.resolved_base_commit
            or document.get("authority")
            != {
                "capital": False,
                "orders": False,
                "promotion": False,
                "self_approval": False,
            }
        ):
            raise AlphaResearchExecutionError(
                "Bulletproof receipt does not match the leased assignment."
            )
        publication_envelope = document.get("publication_envelope")
        if isinstance(publication_envelope, dict):
            publication_envelope = {
                **publication_envelope,
                "task_id": str(task.id),
                "campaign_digest": document["campaign_digest"],
                "source_commit": document["source_commit"],
            }
        qualification_handoff = (
            _qualification_handoff(document["qualification"])
            if "qualification" in document
            else None
        )
        downstream_handoff = {
            **(
                {"publication_envelope": publication_envelope}
                if publication_envelope is not None
                else {}
            ),
            **(
                {"qualification": qualification_handoff}
                if qualification_handoff is not None
                else {}
            ),
        }
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository=contract.repository,
            base_commit=workspace.plan.resolved_base_commit,
            task_attempt=task.attempt_count,
            total_duration_seconds=step.duration_seconds,
            steps=[step],
            success=True,
            worker_version=__version__,
            artifacts=[
                assignment.relative_to(workspace.plan.attempt_directory).as_posix(),
                receipt.relative_to(workspace.plan.attempt_directory).as_posix(),
            ],
            retryable=False,
            downstream_handoff=downstream_handoff,
            summary={
                "disposition": document["disposition"],
                "receipt_digest": document["receipt_digest"],
                "metrics": {
                    key: value
                    for key, value in (document.get("metrics") or {}).items()
                    if key
                    in {
                        "oos_trades",
                        "oos_mean_net_r",
                        "double_cost_oos_mean_net_r",
                        "declared_variant_count",
                        "selected_variant_index",
                        "selection_basis",
                    }
                },
                **(
                    {"alpha_campaign_attempt": document["alpha_campaign_attempt"]}
                    if "alpha_campaign_attempt" in document
                    else {}
                ),
                **(
                    {"hypothesis_card": document["hypothesis_card"]}
                    if "hypothesis_card" in document
                    else {}
                ),
                **(
                    {
                        "qualification_receipt": {
                            "qualified": qualification_handoff.get("qualified"),
                            "card_digest": qualification_handoff.get("card_digest"),
                            "tier": qualification_handoff.get("tier"),
                            "variant_count": qualification_handoff.get("variant_count"),
                        }
                    }
                    if qualification_handoff is not None
                    else {}
                ),
                **(
                    {"engineering_requirement": document["engineering_requirement"]}
                    if "engineering_requirement" in document
                    else {}
                ),
                "production_eligible": False,
                "capital_authority": False,
            },
        )
