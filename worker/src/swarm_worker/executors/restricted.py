from pathlib import Path

from swarm_worker.executors.code_validation import (
    CodeValidationExecutor,
    HeartbeatCallback,
)
from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
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

    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: HeartbeatCallback,
    ) -> WorkflowExecutionResult:
        executor = (
            self._engineering
            if task.task_type == "engineering_mission"
            else self._validation
        )
        return await executor.execute(
            task=task,
            workflow=workflow,
            workspace=workspace,
            heartbeat=heartbeat,
        )
