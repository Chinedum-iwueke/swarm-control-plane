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
from swarm_worker.policy import AlphaDataAdmissionContract
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace


class AlphaDataAdmissionError(RuntimeError):
    """Selected-panel admission failed closed."""


class AlphaDataAdmissionExecutor:
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
            raise RootExecutionError("Alpha data admission must not run as root.")
        contract = AlphaDataAdmissionContract.model_validate(task.input_contract)
        if workflow.name != "alpha-data-admission" or workflow.steps:
            raise AlphaDataAdmissionError(
                "Data-admission workflow identity is invalid."
            )
        if not self._python.is_file():
            raise AlphaDataAdmissionError("Bulletproof virtualenv is unavailable.")
        assignment = workspace.artifacts / "alpha-data-admission-assignment.json"
        output = workspace.artifacts / "alpha-data-admission-receipts.json"
        stdout_path = workspace.logs / "alpha-data-admission.stdout.log"
        stderr_path = workspace.logs / "alpha-data-admission.stderr.log"
        assignment.write_text(
            json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        assignment.chmod(0o600)
        command = (
            str(self._python),
            str(workspace.repository / "scripts/build_alpha_data_admission_batch.py"),
            "--assignment",
            str(assignment),
            "--output",
            str(output),
        )
        started_at = datetime.now(UTC)
        started = time.monotonic()
        env = {
            "PATH": f"{self._python.parent}:/usr/bin:/bin",
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
            deadline = started + workflow.timeout_seconds
            while process.returncode is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.terminate()
                    await process.wait()
                    break
                try:
                    await asyncio.wait_for(
                        asyncio.shield(process.wait()),
                        timeout=min(self._heartbeat_interval, remaining),
                    )
                except TimeoutError:
                    await heartbeat(
                        {
                            "phase": "selected_panel_content_admission",
                            "candidate_id": contract.candidate_id,
                            "asset_count": len(contract.assets),
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                        }
                    )
        ended_at = datetime.now(UTC)
        success = process.returncode == 0 and output.is_file()
        document = json.loads(output.read_text(encoding="utf-8")) if success else {}
        step = StepExecutionResult(
            name="native-selected-panel-admission",
            success=success,
            return_code=process.returncode,
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
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository=contract.repository,
            base_commit=workspace.plan.resolved_base_commit,
            task_attempt=task.attempt_count,
            total_duration_seconds=step.duration_seconds,
            steps=[step],
            success=success,
            termination_reason=None if success else "alpha_data_admission_failed",
            worker_version=__version__,
            artifacts=[output.relative_to(workspace.plan.attempt_directory).as_posix()]
            if output.is_file()
            else [],
            retryable=not success,
            summary={"alpha_data_admission": document} if success else {},
        )
