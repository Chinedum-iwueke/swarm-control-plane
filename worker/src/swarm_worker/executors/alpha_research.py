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


class AlphaResearchExecutor:
    def __init__(
        self,
        *,
        heartbeat_interval_seconds: float,
        effective_uid=os.geteuid,
        python_path: Path = Path(
            "/home/omenka/Projects/bulletproof_bt/.venv/bin/python"
        ),
    ) -> None:
        self._heartbeat_interval = max(5.0, heartbeat_interval_seconds)
        self._effective_uid = effective_uid
        self._python = python_path

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
        env = {
            "PATH": str(self._python.parent) + ":/usr/bin:/bin",
            "HOME": str(workspace.plan.attempt_directory),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(workspace.repository / "src"),
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
            summary={
                "disposition": document["disposition"],
                "receipt_digest": document["receipt_digest"],
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
                    {"qualification": document["qualification"]}
                    if "qualification" in document
                    else {}
                ),
                **(
                    {"engineering_requirement": document["engineering_requirement"]}
                    if "engineering_requirement" in document
                    else {}
                ),
                "publication_envelope": publication_envelope,
                "production_eligible": False,
                "capital_authority": False,
            },
        )
