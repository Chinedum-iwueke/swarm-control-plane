from pathlib import Path

from swarm_worker.config import WorkerSettings
from swarm_worker.executors.alpha_research import AlphaResearchExecutor
from swarm_worker.executors.code_validation import (
    CodeValidationExecutor,
    HeartbeatCallback,
)
from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
from swarm_worker.executors.research_experiment import ResearchExperimentExecutor
from swarm_worker.executors.research_memory_sync import ResearchMemorySyncExecutor
from swarm_worker.models import Task, WorkflowExecutionResult
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace


class RestrictedExecutor:
    def __init__(
        self,
        *,
        codex_home: Path,
        codex_model: str,
        engineering_timeout_seconds: float,
        heartbeat_interval_seconds: float,
        settings: WorkerSettings | None = None,
    ) -> None:
        self._validation = CodeValidationExecutor(
            heartbeat_interval_seconds=heartbeat_interval_seconds
        )
        self._engineering = EngineeringMissionExecutor(
            codex_home=codex_home,
            codex_model=codex_model,
            timeout_seconds=engineering_timeout_seconds,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            validation_executor=self._validation,
        )
        self._research = ResearchExperimentExecutor(
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            validation_executor=self._validation,
        )
        self._memory_sync = (
            ResearchMemorySyncExecutor(settings) if settings is not None else None
        )
        self._alpha_research = AlphaResearchExecutor(
            heartbeat_interval_seconds=heartbeat_interval_seconds
        )

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        executors = {
            "code_validation": self._validation,
            "engineering_mission": self._engineering,
            "research_experiment": self._research,
            "research_memory_sync": self._memory_sync,
            "alpha_research_execution": self._alpha_research,
        }
        executor = executors[task.task_type]
        if executor is None:
            raise RuntimeError("Research-memory synchronization is not configured.")
        return await executor.execute(
            task=task,
            workflow=workflow,
            workspace=workspace,
            heartbeat=heartbeat,
        )
