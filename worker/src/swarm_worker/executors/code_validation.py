from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from swarm_worker import __version__
from swarm_worker.api_client import (
    AuthenticationError,
    ConflictError,
    ConnectionError,
    ServerError,
)
from swarm_worker.models import (
    StepExecutionResult,
    Task,
    WorkflowExecutionResult,
)
from swarm_worker.workflows import (
    UnsafeWorkflowDefinition,
    WorkflowDefinition,
    WorkflowStep,
)
from swarm_worker.workspace import SubprocessRunner, TaskWorkspace

HeartbeatCallback = Callable[[dict[str, object]], Awaitable[None]]
_MAX_HEARTBEAT_FAILURES = 20
_TEST_SECRET_FILES = {
    "POSTGRES_PASSWORD_FILE": "postgres_password",
    "ORCHESTRATOR_SECRET_FILE": "orchestrator_secret",
    "AGENT_TOKEN_SECRET_FILE": "agent_token_secret",
}
_SYNTHETIC_TEST_VALUE = "isolated-worker-test-value"


class ExecutionError(Exception):
    """Base class for restricted workflow execution failures."""


class ExecutionPolicyError(ExecutionError):
    """The supplied task, workflow, or workspace failed closed."""


class RootExecutionError(ExecutionError):
    """Workflow subprocesses must not run with root privileges."""


class LeaseLost(ExecutionError):
    """The control plane no longer recognizes this task lease."""

    def __init__(self, result: WorkflowExecutionResult) -> None:
        super().__init__("Task lease was lost during workflow execution.")
        self.result = result


@dataclass(frozen=True)
class RunningProcess:
    process: asyncio.subprocess.Process
    args: tuple[str, ...]


class AsyncProcessRunner:
    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._environment = dict(SubprocessRunner(environment=environment).environment)

    @property
    def environment(self) -> Mapping[str, str]:
        return dict(self._environment)

    async def start(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        stdout: object,
        stderr: object,
        stdin: object | None = None,
        environment_overrides: Mapping[str, str] | None = None,
    ) -> RunningProcess:
        if isinstance(args, (str, bytes)) or not args:
            raise ValueError("subprocess commands must be argument arrays")
        command = tuple(str(argument) for argument in args)
        environment = dict(self._environment)
        virtualenv_bin = Path(sys.executable).resolve().parent
        existing_path = environment.get("PATH", "")
        environment["PATH"] = os.pathsep.join(
            part for part in (str(virtualenv_bin), existing_path) if part
        )
        environment["VIRTUAL_ENV"] = str(virtualenv_bin.parent)
        python_paths = [cwd]
        backend_path = cwd / "backend"
        if backend_path.is_dir():
            python_paths.append(backend_path)
        environment["HOME"] = str(cwd.parent)
        environment["PYTHONPATH"] = os.pathsep.join(
            str(path) for path in python_paths
        )
        if environment_overrides:
            environment.update(environment_overrides)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            stdin=stdin,
            start_new_session=True,
        )
        return RunningProcess(process=process, args=command)

    async def terminate(
        self,
        running: RunningProcess,
        *,
        grace_seconds: float,
    ) -> None:
        process = running.process
        self._signal_group(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + grace_seconds
        while self._process_group_exists(process.pid) and time.monotonic() < deadline:
            await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

        if self._process_group_exists(process.pid):
            self._signal_group(process.pid, signal.SIGKILL)
        await process.wait()

    @staticmethod
    def _signal_group(pid: int, requested_signal: signal.Signals) -> None:
        try:
            os.killpg(pid, requested_signal)
        except ProcessLookupError:
            pass

    @staticmethod
    def _process_group_exists(pid: int) -> bool:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


class CodeValidationExecutor:
    def __init__(
        self,
        *,
        process_runner: AsyncProcessRunner | None = None,
        step_timeout_seconds: float = 600.0,
        heartbeat_interval_seconds: float = 30.0,
        heartbeat_timeout_seconds: float = 10.0,
        termination_grace_seconds: float = 5.0,
        effective_uid: Callable[[], int] = os.geteuid,
    ) -> None:
        if (
            step_timeout_seconds <= 0
            or heartbeat_interval_seconds <= 0
            or heartbeat_timeout_seconds <= 0
            or termination_grace_seconds <= 0
        ):
            raise ValueError("Executor timeouts must be positive.")
        self._runner = process_runner or AsyncProcessRunner()
        self._step_timeout_seconds = step_timeout_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._termination_grace_seconds = termination_grace_seconds
        self._effective_uid = effective_uid

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        if self._effective_uid() == 0:
            raise RootExecutionError(
                "Refusing to execute workflow subprocesses as root."
            )
        safe_workflow = self._validate_inputs(task, workflow, workspace)
        test_environment = self._prepare_test_environment(workspace)

        workflow_started_at = time.monotonic()
        workflow_deadline = workflow_started_at + safe_workflow.timeout_seconds
        results: list[StepExecutionResult] = []
        heartbeat_failures: list[str] = []
        termination_reason: str | None = None

        for index, step in enumerate(safe_workflow.steps):
            remaining = workflow_deadline - time.monotonic()
            if remaining <= 0:
                termination_reason = "workflow_timeout"
                break

            outcome, lease_lost = await self._execute_step(
                step=step,
                step_index=index,
                total_steps=len(safe_workflow.steps),
                workspace=workspace,
                heartbeat=heartbeat,
                workflow_started_at=workflow_started_at,
                timeout_seconds=min(self._step_timeout_seconds, remaining),
                heartbeat_failures=heartbeat_failures,
                test_environment=test_environment,
            )
            results.append(outcome)
            if lease_lost:
                result = self._result(
                    task=task,
                    workflow=safe_workflow,
                    workspace=workspace,
                    started_at=workflow_started_at,
                    steps=results,
                    heartbeat_failures=heartbeat_failures,
                    success=False,
                    termination_reason="lease_lost",
                )
                raise LeaseLost(result)
            if not outcome.success:
                if outcome.timed_out:
                    termination_reason = (
                        "workflow_timeout"
                        if time.monotonic() >= workflow_deadline
                        else "step_timeout"
                    )
                else:
                    termination_reason = "step_failed"
                break

        success = (
            termination_reason is None
            and len(results) == len(safe_workflow.steps)
            and all(step.success for step in results)
        )
        return self._result(
            task=task,
            workflow=safe_workflow,
            workspace=workspace,
            started_at=workflow_started_at,
            steps=results,
            heartbeat_failures=heartbeat_failures,
            success=success,
            termination_reason=termination_reason,
        )

    async def _execute_step(
        self,
        *,
        step: WorkflowStep,
        step_index: int,
        total_steps: int,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
        workflow_started_at: float,
        timeout_seconds: float,
        heartbeat_failures: list[str],
        test_environment: Mapping[str, str],
    ) -> tuple[StepExecutionResult, bool]:
        stdout_path = workspace.logs / f"{step.name}.stdout.log"
        stderr_path = workspace.logs / f"{step.name}.stderr.log"
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        timed_out = False
        lease_lost = False

        with (
            stdout_path.open("xb") as stdout_file,
            stderr_path.open("xb") as stderr_file,
        ):
            stdout_path.chmod(0o600)
            stderr_path.chmod(0o600)
            running = await self._runner.start(
                step.command,
                cwd=workspace.repository,
                stdout=stdout_file,
                stderr=stderr_file,
                environment_overrides=test_environment,
            )
            deadline = started_monotonic + timeout_seconds

            try:
                while running.process.returncode is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        await self._runner.terminate(
                            running,
                            grace_seconds=self._termination_grace_seconds,
                        )
                        break

                    lease_lost = await self._send_heartbeat(
                        heartbeat=heartbeat,
                        step=step,
                        step_index=step_index,
                        total_steps=total_steps,
                        workflow_started_at=workflow_started_at,
                        heartbeat_failures=heartbeat_failures,
                        timeout_seconds=min(
                            self._heartbeat_timeout_seconds,
                            remaining,
                        ),
                    )
                    if lease_lost:
                        await self._runner.terminate(
                            running,
                            grace_seconds=self._termination_grace_seconds,
                        )
                        break

                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        continue
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(running.process.wait()),
                            timeout=min(
                                self._heartbeat_interval_seconds,
                                remaining,
                            ),
                        )
                    except asyncio.TimeoutError:
                        continue
            except (asyncio.CancelledError, KeyboardInterrupt):
                await asyncio.shield(
                    self._runner.terminate(
                        running,
                        grace_seconds=self._termination_grace_seconds,
                    )
                )
                raise
            except Exception:
                await asyncio.shield(
                    self._runner.terminate(
                        running,
                        grace_seconds=self._termination_grace_seconds,
                    )
                )
                raise

            return_code = running.process.returncode

        ended_at = datetime.now(timezone.utc)
        duration = max(0.0, time.monotonic() - started_monotonic)
        return (
            StepExecutionResult(
                name=step.name,
                success=(return_code == 0 and not timed_out and not lease_lost),
                return_code=return_code,
                started_at=started_at,
                ended_at=ended_at,
                duration_seconds=duration,
                timed_out=timed_out,
                stdout_log=self._relative_log_path(workspace, stdout_path),
                stderr_log=self._relative_log_path(workspace, stderr_path),
            ),
            lease_lost,
        )

    @staticmethod
    def _prepare_test_environment(
        workspace: TaskWorkspace,
    ) -> dict[str, str]:
        secret_directory = workspace.artifacts / "test-secrets"
        secret_directory.mkdir(mode=0o700)
        secret_directory.chmod(0o700)
        environment: dict[str, str] = {
            "APP_ENVIRONMENT": "test",
            "POSTGRES_HOST": "127.0.0.1",
            "REDIS_URL": "redis://127.0.0.1:1/0",
        }
        for variable, filename in _TEST_SECRET_FILES.items():
            secret_path = secret_directory / filename
            secret_path.write_text(_SYNTHETIC_TEST_VALUE, encoding="utf-8")
            secret_path.chmod(0o600)
            environment[variable] = str(secret_path)
        return environment

    async def _send_heartbeat(
        self,
        *,
        heartbeat: HeartbeatCallback,
        step: WorkflowStep,
        step_index: int,
        total_steps: int,
        workflow_started_at: float,
        heartbeat_failures: list[str],
        timeout_seconds: float,
    ) -> bool:
        progress: dict[str, object] = {
            "current_step": step.name,
            "completed_step_count": step_index,
            "total_step_count": total_steps,
            "elapsed_seconds": max(
                0.0,
                time.monotonic() - workflow_started_at,
            ),
        }
        try:
            await asyncio.wait_for(
                heartbeat(progress),
                timeout=timeout_seconds,
            )
        except (AuthenticationError, ConflictError):
            return True
        except (asyncio.TimeoutError, ConnectionError, ServerError) as exc:
            if len(heartbeat_failures) < _MAX_HEARTBEAT_FAILURES:
                heartbeat_failures.append(
                    f"{step.name}: temporary {type(exc).__name__}"
                )
        except Exception as exc:
            raise ExecutionError(
                f"Unexpected heartbeat failure: {type(exc).__name__}"
            ) from exc
        return False

    @staticmethod
    def _validate_inputs(
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
    ) -> WorkflowDefinition:
        try:
            safe_workflow = WorkflowDefinition.model_validate(
                workflow.model_dump(mode="python")
            )
        except ValidationError as exc:
            raise UnsafeWorkflowDefinition(
                "Workflow failed execution-boundary validation."
            ) from exc

        plan = workspace.plan
        metadata = workspace.metadata
        try:
            repository_path = plan.workspace_repository.resolve(strict=True)
            logs_path = plan.logs_directory.resolve(strict=True)
            attempt_path = plan.attempt_directory.resolve(strict=True)
        except OSError as exc:
            raise ExecutionPolicyError("Prepared workspace paths are missing.") from exc

        if (
            task.task_type not in {"code_validation", "engineering_mission"}
            or safe_workflow.task_type != task.task_type
            or plan.task_id != task.id
            or plan.task_number != task.task_number
            or plan.attempt_number != task.attempt_count
            or plan.repository not in safe_workflow.allowed_repositories
            or metadata.task_id != plan.task_id
            or metadata.task_number != plan.task_number
            or metadata.attempt_number != plan.attempt_number
            or metadata.repository != plan.repository
            or metadata.workspace_repository != plan.workspace_repository
            or metadata.resolved_base_commit != plan.resolved_base_commit
            or repository_path != plan.workspace_repository
            or attempt_path not in repository_path.parents
            or attempt_path not in logs_path.parents
        ):
            raise ExecutionPolicyError(
                "Task, workflow, and workspace ownership do not match."
            )
        return safe_workflow

    @staticmethod
    def _relative_log_path(
        workspace: TaskWorkspace,
        log_path: Path,
    ) -> str:
        return log_path.relative_to(workspace.plan.attempt_directory).as_posix()

    @staticmethod
    def _result(
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        started_at: float,
        steps: list[StepExecutionResult],
        heartbeat_failures: list[str],
        success: bool,
        termination_reason: str | None,
    ) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository=workspace.plan.repository,
            base_commit=workspace.plan.resolved_base_commit,
            task_attempt=task.attempt_count,
            total_duration_seconds=max(0.0, time.monotonic() - started_at),
            steps=steps,
            success=success,
            heartbeat_failures=heartbeat_failures,
            termination_reason=termination_reason,
            worker_version=__version__,
        )
