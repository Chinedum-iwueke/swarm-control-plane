from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import UTC, datetime
from time import monotonic

from swarm_worker import __version__
from swarm_worker.api_client import (
    AuthenticationError,
    ConflictError,
    ConnectionError,
    ServerError,
    SwarmAPIClient,
)
from swarm_worker.config import WorkerSettings
from swarm_worker.executors.code_validation import HeartbeatCallback, LeaseLost
from swarm_worker.models import (
    ResearchMemoryRegistrationRequest,
    StepExecutionResult,
    Task,
    WorkflowExecutionResult,
)
from swarm_worker.research_memory_bridge import (
    build_export,
    canonical_digest,
    memory_summary,
)
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace


class ResearchMemorySyncExecutor:
    def __init__(self, settings: WorkerSettings) -> None:
        self._settings = settings
        self._heartbeat_interval = settings.swarm_task_heartbeat_seconds

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        started_at = datetime.now(UTC)
        started = monotonic()
        stop_event = threading.Event()
        repository = self._settings.swarm_repository_root / "bulletproof_bt"
        database = repository / "research_db" / "research.sqlite"
        build = asyncio.create_task(
            asyncio.to_thread(
                build_export,
                repository,
                database,
                stop_event=stop_event,
            )
        )
        heartbeat_failures: list[str] = []
        try:
            while not build.done():
                if monotonic() - started >= workflow.timeout_seconds:
                    stop_event.set()
                    try:
                        await build
                    except InterruptedError:
                        pass
                    raise TimeoutError(
                        "Research-memory synchronization exceeded its workflow timeout."
                    )
                done, _ = await asyncio.wait(
                    {build},
                    timeout=min(
                        self._heartbeat_interval,
                        max(0.1, workflow.timeout_seconds - (monotonic() - started)),
                    ),
                )
                if done:
                    break
                try:
                    await heartbeat(
                        {
                            "current_step": "digest-research-memory",
                            "completed_step_count": 0,
                            "total_step_count": 1,
                            "elapsed_seconds": round(monotonic() - started, 3),
                        }
                    )
                except (AuthenticationError, ConflictError) as exc:
                    stop_event.set()
                    try:
                        await build
                    except InterruptedError:
                        pass
                    raise LeaseLost("Task lease was lost during memory sync.") from exc
                except (ConnectionError, ServerError) as exc:
                    heartbeat_failures.append(type(exc).__name__)
            document = await build
        except (asyncio.CancelledError, KeyboardInterrupt):
            stop_event.set()
            try:
                await build
            except (InterruptedError, asyncio.CancelledError):
                pass
            raise

        export = document.model_dump(mode="json")
        export_digest = canonical_digest(export)
        summary = memory_summary(document, export_digest)
        summary_digest = hashlib.sha256(summary.encode()).hexdigest()
        async with SwarmAPIClient(self._settings) as api:
            registration = await api.register_research_memory(
                ResearchMemoryRegistrationRequest(
                    export=export,
                    export_digest=export_digest,
                    summary=summary,
                    summary_digest=summary_digest,
                )
            )
        ended_at = datetime.now(UTC)
        duration = monotonic() - started
        logs = workspace.plan.logs_directory
        logs.mkdir(parents=True, exist_ok=True, mode=0o700)
        stdout = logs / "sync-research-memory.stdout.log"
        stderr = logs / "sync-research-memory.stderr.log"
        result = {
            "export_digest": export_digest,
            "export_id": registration.export["id"],
            "document_key": registration.document_key,
            "unchanged": registration.unchanged,
            "counts": document.counts.model_dump(),
        }
        stdout.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        stderr.write_text("")
        stdout.chmod(0o600)
        stderr.chmod(0o600)
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository="bulletproof_bt",
            base_commit=document.repository_commit,
            task_attempt=task.attempt_count,
            total_duration_seconds=duration,
            steps=[
                StepExecutionResult(
                    name="sync-research-memory",
                    success=True,
                    return_code=0,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=duration,
                    stdout_log="logs/sync-research-memory.stdout.log",
                    stderr_log="logs/sync-research-memory.stderr.log",
                )
            ],
            success=True,
            heartbeat_failures=heartbeat_failures[:20],
            worker_version=__version__,
            summary=result,
        )
