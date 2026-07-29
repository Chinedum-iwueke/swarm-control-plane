from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from swarm_worker.api_client import (
    AuthenticationError,
    ConflictError,
    SwarmAPIClient,
    WorkerAPIError,
)
from swarm_worker.config import WorkerSettings
from swarm_worker.executors.code_validation import (
    CodeValidationExecutor,
    LeaseLost,
)
from swarm_worker.models import (
    AgentHeartbeat,
    AgentHeartbeatResponse,
    AgentIdentity,
    LeaseResponse,
    Task,
    TaskCompleteRequest,
    TaskExecutionHeartbeatRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskMutationResponse,
    TaskReleaseRequest,
    TaskStartRequest,
    WorkflowExecutionResult,
)
from swarm_worker.policy import (
    ValidatedTaskPolicy,
    WorkerPolicyError,
    validate_task_policy,
)
from swarm_worker.workflows import (
    WorkflowDefinition,
    WorkflowLoader,
    WorkflowPolicyError,
)
from swarm_worker.workspace import TaskWorkspace, WorkspaceManager


class WorkerServiceError(Exception):
    """Base class for single-cycle orchestration failures."""


class WorkerConfigurationError(WorkerServiceError):
    """Worker environment configuration is invalid."""


class IdentityMismatch(WorkerServiceError):
    """The authenticated identity does not match worker configuration."""


class AgentDisabled(WorkerServiceError):
    """The authenticated worker agent is disabled."""


class InvalidLeaseResponse(WorkerServiceError):
    """The lease response contained an invalid task/token combination."""


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoWorkOutcome(ResultModel):
    status: Literal["no_work"] = "no_work"


class SucceededOutcome(ResultModel):
    status: Literal["succeeded"] = "succeeded"
    task_id: UUID
    task_number: str
    workspace: Path
    result: WorkflowExecutionResult


class FailedOutcome(ResultModel):
    status: Literal["failed"] = "failed"
    task_id: UUID
    task_number: str
    workspace: Path
    failure: dict[str, object]
    retryable: bool


class ReleasedOutcome(ResultModel):
    status: Literal["released"] = "released"
    task_id: UUID
    task_number: str
    reason_category: str


class LeaseLostOutcome(ResultModel):
    status: Literal["lease_lost"] = "lease_lost"
    task_id: UUID
    task_number: str
    phase: str
    workspace: Path | None = None


RunOnceOutcome = (
    NoWorkOutcome
    | SucceededOutcome
    | FailedOutcome
    | ReleasedOutcome
    | LeaseLostOutcome
)


class AgentAPI(Protocol):
    async def aclose(self) -> None: ...

    async def get_identity(self) -> AgentIdentity: ...

    async def send_agent_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeatResponse: ...

    async def lease_task(self, request: TaskLeaseRequest) -> LeaseResponse: ...

    async def start_task(
        self,
        task_id: UUID | str,
        request: TaskStartRequest,
    ) -> TaskMutationResponse: ...

    async def heartbeat_task(
        self,
        task_id: UUID | str,
        request: TaskExecutionHeartbeatRequest,
    ) -> TaskMutationResponse: ...

    async def complete_task(
        self,
        task_id: UUID | str,
        request: TaskCompleteRequest,
    ) -> TaskMutationResponse: ...

    async def fail_task(
        self,
        task_id: UUID | str,
        request: TaskFailRequest,
    ) -> TaskMutationResponse: ...

    async def release_task(
        self,
        task_id: UUID | str,
        request: TaskReleaseRequest,
    ) -> TaskMutationResponse: ...


class WorkspacePreparer(Protocol):
    def prepare(
        self,
        *,
        task_id: UUID,
        task_number: str,
        attempt_number: int,
        repository: str,
        base_ref: str,
        validation_only: bool = False,
    ) -> TaskWorkspace: ...


class WorkflowExecutor(Protocol):
    async def execute(
        self,
        *,
        task: Task,
        workflow: WorkflowDefinition,
        workspace: TaskWorkspace,
        heartbeat: Callable[[dict[str, object]], Awaitable[None]],
    ) -> WorkflowExecutionResult: ...


SettingsLoader = Callable[[], WorkerSettings]
APIClientFactory = Callable[[WorkerSettings], AgentAPI]
WorkflowLoaderFactory = Callable[[WorkerSettings], WorkflowLoader]
WorkspaceManagerFactory = Callable[[WorkerSettings], WorkspacePreparer]
ExecutorFactory = Callable[[WorkerSettings], WorkflowExecutor]
PolicyValidator = Callable[..., ValidatedTaskPolicy]


def _default_workflow_loader(settings: WorkerSettings) -> WorkflowLoader:
    return WorkflowLoader(settings.swarm_workflow_directory)


def _default_workspace_manager(settings: WorkerSettings) -> WorkspaceManager:
    return WorkspaceManager(
        settings.swarm_repository_root,
        settings.swarm_workspace_root,
    )


def _default_executor(settings: WorkerSettings) -> CodeValidationExecutor:
    return CodeValidationExecutor(
        heartbeat_interval_seconds=settings.swarm_task_heartbeat_seconds,
    )


class WorkerService:
    def __init__(
        self,
        *,
        settings_loader: SettingsLoader = WorkerSettings,
        api_client_factory: APIClientFactory = SwarmAPIClient,
        workflow_loader_factory: WorkflowLoaderFactory = _default_workflow_loader,
        workspace_manager_factory: WorkspaceManagerFactory = (
            _default_workspace_manager
        ),
        executor_factory: ExecutorFactory = _default_executor,
        policy_validator: PolicyValidator = validate_task_policy,
    ) -> None:
        self._settings_loader = settings_loader
        self._api_client_factory = api_client_factory
        self._workflow_loader_factory = workflow_loader_factory
        self._workspace_manager_factory = workspace_manager_factory
        self._executor_factory = executor_factory
        self._policy_validator = policy_validator

    async def run_once(self) -> RunOnceOutcome:
        settings = self._load_settings()
        settings.prepare_directories()
        api = self._api_client_factory(settings)
        task = None
        lease_token: str | None = None
        started = False

        try:
            identity = await api.get_identity()
            self._validate_identity(identity, settings)
            heartbeat_response = await api.send_agent_heartbeat(
                AgentHeartbeat(
                    status="idle",
                    runtime="hermes",
                    capabilities=identity.capabilities,
                    metadata={
                        "agent_slug": settings.swarm_agent_slug,
                        "machine": settings.swarm_machine,
                    },
                )
            )
            if (
                heartbeat_response.status != "idle"
                or heartbeat_response.presence != "online"
            ):
                raise WorkerServiceError(
                    "Control plane did not confirm idle online presence."
                )

            lease = await api.lease_task(
                TaskLeaseRequest(lease_seconds=settings.swarm_lease_seconds)
            )
            if lease.task is None and lease.lease_token is None:
                return NoWorkOutcome()
            if lease.task is None or lease.lease_token is None:
                raise InvalidLeaseResponse(
                    "Control plane returned an incomplete task lease."
                )
            task = lease.task
            lease_token = lease.lease_token

            try:
                workflow_loader = self._workflow_loader_factory(settings)
                validated = self._policy_validator(
                    task,
                    identity,
                    workflow_loader,
                    worker_machine=settings.swarm_machine,
                )
                if not isinstance(validated, ValidatedTaskPolicy):
                    raise TypeError("Policy validator returned an invalid result.")
            except (WorkerPolicyError, WorkflowPolicyError) as exc:
                return await self._release_or_lease_lost(
                    api=api,
                    task_id=task.id,
                    task_number=task.task_number,
                    lease_token=lease_token,
                    category=type(exc).__name__,
                    phase="policy_release",
                )
            except Exception as exc:  # noqa: BLE001 - injected policy boundary
                return await self._release_or_lease_lost(
                    api=api,
                    task_id=task.id,
                    task_number=task.task_number,
                    lease_token=lease_token,
                    category=f"policy_{type(exc).__name__}",
                    phase="policy_release",
                )

            try:
                workspace_manager = self._workspace_manager_factory(settings)
                workspace = workspace_manager.prepare(
                    task_id=task.id,
                    task_number=task.task_number,
                    attempt_number=task.attempt_count,
                    repository=validated.contract.repository,
                    base_ref=validated.contract.base_ref,
                )
                if not isinstance(workspace, TaskWorkspace):
                    raise TypeError("Workspace manager returned an invalid result.")
            except Exception as exc:  # noqa: BLE001 - workspace boundary
                return await self._release_or_lease_lost(
                    api=api,
                    task_id=task.id,
                    task_number=task.task_number,
                    lease_token=lease_token,
                    category=f"workspace_{type(exc).__name__}",
                    phase="workspace_release",
                )

            try:
                await api.start_task(
                    task.id,
                    TaskStartRequest(
                        lease_token=lease_token,
                        message="Restricted worker started task execution.",
                    ),
                )
            except (AuthenticationError, ConflictError):
                return self._lease_lost(task, "start", workspace)
            started = True

            async def send_task_heartbeat(
                progress: dict[str, object],
            ) -> None:
                await api.heartbeat_task(
                    task.id,
                    TaskExecutionHeartbeatRequest(
                        lease_token=lease_token,
                        lease_seconds=settings.swarm_lease_seconds,
                        message="Restricted worker task heartbeat.",
                        progress=progress,
                    ),
                )

            try:
                executor = self._executor_factory(settings)
                execution_result = await executor.execute(
                    task=task,
                    workflow=validated.workflow,
                    workspace=workspace,
                    heartbeat=send_task_heartbeat,
                )
                execution_result = WorkflowExecutionResult.model_validate(
                    execution_result.model_dump(mode="python")
                )
            except LeaseLost:
                return self._lease_lost(task, "execution", workspace)
            except Exception as exc:  # noqa: BLE001 - executor boundary
                return await self._fail_or_lease_lost(
                    api=api,
                    task=task,
                    lease_token=lease_token,
                    workspace=workspace,
                    category=f"executor_{type(exc).__name__}",
                    failed_step=None,
                    return_code=None,
                    stdout_log=None,
                    stderr_log=None,
                    retryable=False,
                )

            if not execution_result.success:
                failed_step = next(
                    (
                        step
                        for step in reversed(execution_result.steps)
                        if not step.success
                    ),
                    None,
                )
                category = execution_result.termination_reason or "step_failed"
                return await self._fail_or_lease_lost(
                    api=api,
                    task=task,
                    lease_token=lease_token,
                    workspace=workspace,
                    category=category,
                    failed_step=(failed_step.name if failed_step is not None else None),
                    return_code=(
                        failed_step.return_code if failed_step is not None else None
                    ),
                    stdout_log=(
                        failed_step.stdout_log if failed_step is not None else None
                    ),
                    stderr_log=(
                        failed_step.stderr_log if failed_step is not None else None
                    ),
                    retryable=category
                    in {
                        "step_timeout",
                        "workflow_timeout",
                    },
                )

            try:
                await api.complete_task(
                    task.id,
                    TaskCompleteRequest(
                        lease_token=lease_token,
                        message="Restricted validation workflow succeeded.",
                        result=execution_result.model_dump(mode="json"),
                    ),
                )
            except (AuthenticationError, ConflictError):
                return self._lease_lost(task, "complete", workspace)

            return SucceededOutcome(
                task_id=task.id,
                task_number=task.task_number,
                workspace=workspace.plan.attempt_directory,
                result=execution_result,
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            if task is not None and lease_token is not None:
                await self._release_after_cancellation(
                    api,
                    task.id,
                    lease_token,
                    started=started,
                )
            raise
        finally:
            await api.aclose()

    def _load_settings(self) -> WorkerSettings:
        try:
            settings = self._settings_loader()
        except PydanticValidationError:
            raise WorkerConfigurationError("Worker configuration is invalid.") from None
        if not isinstance(settings, WorkerSettings):
            raise WorkerConfigurationError(
                "Settings loader returned an invalid configuration."
            )
        return settings

    @staticmethod
    def _validate_identity(
        identity: AgentIdentity,
        settings: WorkerSettings,
    ) -> None:
        if not identity.is_enabled:
            raise AgentDisabled("Authenticated agent is disabled.")
        if (
            identity.slug != settings.swarm_agent_slug
            or identity.machine != settings.swarm_machine
        ):
            raise IdentityMismatch(
                "Authenticated identity does not match worker configuration."
            )

    @staticmethod
    def _lease_lost(
        task: Task,
        phase: str,
        workspace: TaskWorkspace | None,
    ) -> LeaseLostOutcome:
        return LeaseLostOutcome(
            task_id=task.id,
            task_number=task.task_number,
            phase=phase,
            workspace=(
                workspace.plan.attempt_directory if workspace is not None else None
            ),
        )

    async def _release_or_lease_lost(
        self,
        *,
        api: AgentAPI,
        task_id: UUID,
        task_number: str,
        lease_token: str,
        category: str,
        phase: str,
    ) -> ReleasedOutcome | LeaseLostOutcome:
        try:
            await api.release_task(
                task_id,
                TaskReleaseRequest(
                    lease_token=lease_token,
                    message=(
                        "Restricted worker released task before start: "
                        f"{category[:100]}."
                    ),
                ),
            )
        except (AuthenticationError, ConflictError):
            return LeaseLostOutcome(
                task_id=task_id,
                task_number=task_number,
                phase=phase,
            )
        return ReleasedOutcome(
            task_id=task_id,
            task_number=task_number,
            reason_category=category[:100],
        )

    async def _fail_or_lease_lost(
        self,
        *,
        api: AgentAPI,
        task: Task,
        lease_token: str,
        workspace: TaskWorkspace,
        category: str,
        failed_step: str | None,
        return_code: int | None,
        stdout_log: str | None,
        stderr_log: str | None,
        retryable: bool,
    ) -> FailedOutcome | LeaseLostOutcome:
        failure: dict[str, object] = {
            "error_category": category[:100],
            "failed_step": failed_step,
            "return_code": return_code,
            "stdout_log": stdout_log,
            "stderr_log": stderr_log,
            "retryable": retryable,
        }
        try:
            await api.fail_task(
                task.id,
                TaskFailRequest(
                    lease_token=lease_token,
                    message="Restricted validation workflow failed.",
                    failure=failure,
                    retryable=retryable,
                ),
            )
        except (AuthenticationError, ConflictError):
            return self._lease_lost(task, "fail", workspace)
        return FailedOutcome(
            task_id=task.id,
            task_number=task.task_number,
            workspace=workspace.plan.attempt_directory,
            failure=failure,
            retryable=retryable,
        )

    @staticmethod
    async def _release_after_cancellation(
        api: AgentAPI,
        task_id: UUID,
        lease_token: str,
        *,
        started: bool,
    ) -> None:
        release = asyncio.create_task(
            api.release_task(
                task_id,
                TaskReleaseRequest(
                    lease_token=lease_token,
                    message=(
                        "Restricted worker released task after cancellation "
                        f"({'running' if started else 'leased'})."
                    ),
                ),
            )
        )
        try:
            await asyncio.shield(release)
        except WorkerAPIError:
            pass
