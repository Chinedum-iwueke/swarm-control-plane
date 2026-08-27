import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from swarm_worker import __version__
from swarm_worker.api_client import AuthenticationError, ConflictError
from swarm_worker.config import WorkerSettings
from swarm_worker.executors.code_validation import LeaseLost
from swarm_worker.models import (
    AgentContextManifest,
    AgentHeartbeatResponse,
    AgentIdentity,
    LeaseResponse,
    StepExecutionResult,
    Task,
    WorkflowExecutionResult,
)
from swarm_worker.policy import (
    CodeValidationContract,
    RepositoryNotAllowed,
    ValidatedTaskPolicy,
)
from swarm_worker.role_package import load_role_package
from swarm_worker.service import (
    AgentDisabled,
    FailedOutcome,
    IdentityMismatch,
    LeaseLostOutcome,
    NoWorkOutcome,
    PausedOutcome,
    ReleasedOutcome,
    SucceededOutcome,
    WorkerConfigurationError,
    WorkerService,
)
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import (
    TaskWorkspace,
    WorkspaceMetadata,
    WorkspacePlan,
)

AGENT_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
LEASE_TOKEN = "swarm_lt_abcdef_service-lease-token"
AGENT_TOKEN = "swarm_ag_abcdef_service-agent-token"


def verified_role_package():
    package = load_role_package(
        Path(
            "/home/omenka/Projects/swarm-control-plane/worker/"
            "role-packages/vm1-engineering-worker/manifest.yaml"
        ),
        Path("/home/omenka/Projects/swarm-control-plane/worker/workflows"),
    )
    package.manifest.repository_profile.repositories.append("project")
    return package


NOW = "2026-07-29T12:00:00Z"


def make_settings(tmp_path: Path) -> WorkerSettings:
    return WorkerSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token=AGENT_TOKEN,
        swarm_workspace_root=tmp_path / "workspaces",
        swarm_repository_root=tmp_path / "repositories",
        swarm_workflow_directory=tmp_path / "workflows",
        swarm_task_heartbeat_seconds=0.1,
    )


def make_identity(**changes: Any) -> AgentIdentity:
    values = {
        "id": AGENT_ID,
        "slug": "vm1-developer-coder",
        "display_name": "VM1 Developer Coder",
        "role": "developer",
        "machine": "vm1-developer",
        "hermes_profile": "restricted",
        "runtime": "hermes",
        "runtime_version": "1.0",
        "status": "idle",
        "presence": "online",
        "capabilities": ["code_validation", "git", "python", "testing"],
        "heartbeat_metadata": {},
        "risk_ceiling": 1,
        "is_enabled": True,
        "last_heartbeat_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return AgentIdentity.model_validate(values)


def make_task(**changes: Any) -> Task:
    values = {
        "id": TASK_ID,
        "task_number": "TASK-1",
        "project": "swarm-control-plane",
        "task_type": "code_validation",
        "title": "Validate code",
        "objective": "Run restricted validation.",
        "status": "leased",
        "priority": 50,
        "risk_level": 1,
        "assigned_agent_id": AGENT_ID,
        "parent_task_id": None,
        "created_by": "orchestrator",
        "input_contract": {
            "repository": "project",
            "workflow": "code-validation",
            "base_ref": "main",
        },
        "expected_outputs": [],
        "acceptance_criteria": [],
        "approval_policy": {},
        "required_capabilities": ["code_validation"],
        "allowed_machines": ["vm1-developer"],
        "max_attempts": 3,
        "attempt_count": 1,
        "leased_at": NOW,
        "lease_expires_at": NOW,
        "last_execution_heartbeat_at": NOW,
        "result": {},
        "failure": {},
        "created_at": NOW,
        "updated_at": NOW,
        "started_at": None,
        "completed_at": None,
    }
    values.update(changes)
    return Task.model_validate(values)


def make_workflow() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "name": "code-validation",
            "task_type": "code_validation",
            "timeout_seconds": 900,
            "allowed_repositories": ["project"],
            "steps": [{"name": "run-tests", "command": ["pytest", "-q"]}],
        }
    )


def make_validated_policy() -> ValidatedTaskPolicy:
    return ValidatedTaskPolicy(
        contract=CodeValidationContract(
            repository="project",
            workflow="code-validation",
            base_ref="main",
        ),
        workflow=make_workflow(),
    )


def make_workspace(tmp_path: Path) -> TaskWorkspace:
    attempt = tmp_path / "workspaces" / "TASK-1-id" / "attempt-1"
    repository = attempt / "repository"
    logs = attempt / "logs"
    artifacts = attempt / "artifacts"
    repository.mkdir(parents=True, exist_ok=True)
    logs.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    (logs / "run-tests.stdout.log").write_text("passed\n", encoding="utf-8")
    (logs / "run-tests.stderr.log").write_text("", encoding="utf-8")
    plan = WorkspacePlan(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        source_repository=tmp_path / "repositories" / "project",
        attempt_directory=attempt,
        workspace_repository=repository,
        logs_directory=logs,
        artifacts_directory=artifacts,
        metadata_path=attempt / "metadata.json",
        base_ref="main",
        resolved_base_commit="a" * 40,
    )
    metadata = WorkspaceMetadata(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        source_repository=plan.source_repository,
        workspace_repository=repository,
        base_ref="main",
        resolved_base_commit=plan.resolved_base_commit,
        created_at=datetime.now(timezone.utc),
    )
    return TaskWorkspace(plan=plan, metadata=metadata)


def make_execution_result(*, success: bool = True) -> WorkflowExecutionResult:
    step = StepExecutionResult(
        name="run-tests",
        success=success,
        return_code=0 if success else 1,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=0.25,
        stdout_log="logs/run-tests.stdout.log",
        stderr_log="logs/run-tests.stderr.log",
    )
    return WorkflowExecutionResult(
        workflow="code-validation",
        repository="project",
        base_commit="a" * 40,
        task_attempt=1,
        total_duration_seconds=0.25,
        steps=[step],
        success=success,
        termination_reason=None if success else "step_failed",
    )


class FakeAPI:
    def __init__(
        self,
        events: list[str],
        *,
        identity: AgentIdentity | None = None,
        lease: LeaseResponse | None = None,
        identity_error: Exception | None = None,
        start_error: Exception | None = None,
        complete_error: Exception | None = None,
        fail_error: Exception | None = None,
        release_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.identity = identity or make_identity()
        self.lease = lease or LeaseResponse(
            task=make_task(),
            lease_token=LEASE_TOKEN,
        )
        self.identity_error = identity_error
        self.start_error = start_error
        self.complete_error = complete_error
        self.fail_error = fail_error
        self.release_error = release_error
        self.requests: dict[str, list[object]] = {
            "complete": [],
            "fail": [],
            "release": [],
            "heartbeat_task": [],
        }
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def get_identity(self) -> AgentIdentity:
        self.events.append("identity")
        if self.identity_error:
            raise self.identity_error
        return self.identity

    async def send_agent_heartbeat(self, heartbeat: object):
        self.events.append("agent_heartbeat")
        assert heartbeat.status == "idle"
        assert heartbeat.runtime_version == __version__
        assert heartbeat.metadata["worker_version"] == __version__
        return AgentHeartbeatResponse(
            agent_id=AGENT_ID,
            status="idle",
            presence="online",
            received_at=datetime.now(timezone.utc),
        )

    async def lease_task(self, request: object) -> LeaseResponse:
        self.events.append("lease")
        assert request.lease_seconds == 300
        return self.lease

    async def start_task(self, task_id: UUID, request: object) -> object:
        self.events.append("start")
        assert request.lease_token == LEASE_TOKEN
        if self.start_error:
            raise self.start_error
        return object()

    async def get_task_context(self, task_id: UUID, lease_token: str):
        self.events.append("context")
        assert lease_token == LEASE_TOKEN
        return AgentContextManifest(
            id=UUID("33333333-3333-4333-8333-333333333333"),
            task_id=task_id,
            agent_id=AGENT_ID,
            attempt_number=1,
            schema_version="agent-context-manifest-v1.0.0",
            purpose="Bounded test context.",
            authorization_snapshot_digest="a" * 64,
            items=[],
            context_pack_digest="b" * 64,
            manifest_digest="c" * 64,
            item_count=0,
            byte_count=100,
            status="locked",
            expires_at=datetime.now(timezone.utc),
            created_by="founder-operator",
            created_at=datetime.now(timezone.utc),
        )

    async def heartbeat_task(self, task_id: UUID, request: object) -> object:
        self.events.append("task_heartbeat")
        self.requests["heartbeat_task"].append(request)
        return object()

    async def complete_task(self, task_id: UUID, request: object) -> object:
        self.events.append("complete")
        self.requests["complete"].append(request)
        if self.complete_error:
            raise self.complete_error
        return object()

    async def register_artifact(self, task_id: UUID, request: object) -> object:
        self.requests.setdefault("artifacts", []).append(request)
        return object()

    async def fail_task(self, task_id: UUID, request: object) -> object:
        self.events.append("fail")
        self.requests["fail"].append(request)
        if self.fail_error:
            raise self.fail_error
        return object()

    async def release_task(self, task_id: UUID, request: object) -> object:
        self.events.append("release")
        self.requests["release"].append(request)
        if self.release_error:
            raise self.release_error
        return object()


class FakeWorkspaceManager:
    def __init__(
        self,
        events: list[str],
        workspace: TaskWorkspace,
        *,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.workspace = workspace
        self.error = error

    def prepare(self, **kwargs: object) -> TaskWorkspace:
        self.events.append("prepare")
        if self.error:
            raise self.error
        return self.workspace


class FakeExecutor:
    def __init__(
        self,
        events: list[str],
        result: WorkflowExecutionResult,
        *,
        error: Exception | None = None,
        invoke_heartbeat: bool = False,
    ) -> None:
        self.events = events
        self.result = result
        self.error = error
        self.invoke_heartbeat = invoke_heartbeat

    async def execute(self, **kwargs: object) -> WorkflowExecutionResult:
        self.events.append("execute")
        if self.invoke_heartbeat:
            heartbeat = kwargs["heartbeat"]
            await heartbeat({"current_step": "run-tests"})
        if self.error:
            raise self.error
        return self.result


def make_service(
    tmp_path: Path,
    api: FakeAPI,
    events: list[str],
    *,
    execution_result: WorkflowExecutionResult | None = None,
    executor_error: Exception | None = None,
    workspace_error: Exception | None = None,
    policy_error: Exception | None = None,
    invoke_heartbeat: bool = False,
) -> WorkerService:
    settings = make_settings(tmp_path)
    workspace = make_workspace(tmp_path)
    manager = FakeWorkspaceManager(
        events,
        workspace,
        error=workspace_error,
    )
    fake_executor = FakeExecutor(
        events,
        execution_result or make_execution_result(),
        error=executor_error,
        invoke_heartbeat=invoke_heartbeat,
    )

    def validate(*args: object, **kwargs: object) -> ValidatedTaskPolicy:
        events.append("validate")
        if policy_error:
            raise policy_error
        return make_validated_policy()

    return WorkerService(
        settings_loader=lambda: settings,
        api_client_factory=lambda current: api,
        workflow_loader_factory=lambda current: object(),
        workspace_manager_factory=lambda current: manager,
        executor_factory=lambda current: fake_executor,
        policy_validator=validate,
        role_package_loader=lambda current: verified_role_package(),
    )


@pytest.mark.asyncio
async def test_happy_path_exact_order_and_complete_once(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    service = make_service(tmp_path, api, events)

    outcome = await service.run_once()

    assert isinstance(outcome, SucceededOutcome)
    assert events == [
        "identity",
        "agent_heartbeat",
        "lease",
        "validate",
        "prepare",
        "start",
        "execute",
        "complete",
    ]
    assert len(api.requests["complete"]) == 1
    assert len(api.requests["fail"]) == 0
    assert len(api.requests["artifacts"]) == 2
    assert api.requests["artifacts"][0].location.startswith("workspace://")
    assert api.closed is True


@pytest.mark.asyncio
async def test_governed_context_is_fetched_and_materialized_before_start(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    task = make_task(
        input_contract={
            "repository": "project",
            "workflow": "code-validation",
            "base_ref": "main",
            "governed_context_required": True,
        }
    )
    api = FakeAPI(events, lease=LeaseResponse(task=task, lease_token=LEASE_TOKEN))
    outcome = await make_service(tmp_path, api, events).run_once()

    assert isinstance(outcome, SucceededOutcome)
    assert events.index("context") < events.index("start")
    context_path = outcome.workspace / "context-manifest.json"
    assert context_path.exists()
    assert context_path.stat().st_mode & 0o777 == 0o600
    assert '"manifest_digest": "cccc' in context_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_failure_path_exact_order_and_fail_once(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    service = make_service(
        tmp_path,
        api,
        events,
        execution_result=make_execution_result(success=False),
    )

    outcome = await service.run_once()

    assert isinstance(outcome, FailedOutcome)
    assert events == [
        "identity",
        "agent_heartbeat",
        "lease",
        "validate",
        "prepare",
        "start",
        "execute",
        "fail",
    ]
    assert len(api.requests["fail"]) == 1
    assert len(api.requests["complete"]) == 0
    assert outcome.failure == {
        "error_category": "step_failed",
        "failed_step": "run-tests",
        "return_code": 1,
        "stdout_log": "logs/run-tests.stdout.log",
        "stderr_log": "logs/run-tests.stderr.log",
        "retryable": False,
        "worker_version": __version__,
    }


@pytest.mark.asyncio
async def test_policy_rejection_releases_before_start(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    service = make_service(
        tmp_path,
        api,
        events,
        policy_error=RepositoryNotAllowed("not allowed"),
    )

    outcome = await service.run_once()

    assert isinstance(outcome, ReleasedOutcome)
    assert events == [
        "identity",
        "agent_heartbeat",
        "lease",
        "validate",
        "release",
    ]
    assert not api.requests["fail"]
    assert not api.requests["complete"]


@pytest.mark.asyncio
async def test_no_available_task_is_clean_no_work(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(
        events,
        lease=LeaseResponse(task=None, lease_token=None),
    )

    outcome = await make_service(tmp_path, api, events).run_once()

    assert isinstance(outcome, NoWorkOutcome)
    assert events == ["identity", "agent_heartbeat", "lease"]
    assert api.closed is True


@pytest.mark.asyncio
async def test_paused_worker_does_not_validate_or_prepare(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(
        events,
        lease=LeaseResponse(
            task=None,
            lease_token=None,
            paused=True,
            pause_reasons=["maintenance"],
        ),
    )

    outcome = await make_service(tmp_path, api, events).run_once()

    assert isinstance(outcome, PausedOutcome)
    assert outcome.reasons == ["maintenance"]
    assert events == ["identity", "agent_heartbeat", "lease"]


@pytest.mark.asyncio
async def test_authentication_failure_propagates_and_closes(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(
        events,
        identity_error=AuthenticationError("credential rejected"),
    )

    with pytest.raises(AuthenticationError):
        await make_service(tmp_path, api, events).run_once()

    assert events == ["identity"]
    assert api.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identity", "exception_type"),
    [
        (make_identity(slug="another-agent"), IdentityMismatch),
        (make_identity(machine="vm2-reviewer"), IdentityMismatch),
        (make_identity(is_enabled=False), AgentDisabled),
    ],
)
async def test_invalid_identity_stops_before_heartbeat_and_lease(
    tmp_path: Path,
    identity: AgentIdentity,
    exception_type: type[Exception],
) -> None:
    events: list[str] = []
    api = FakeAPI(events, identity=identity)

    with pytest.raises(exception_type):
        await make_service(tmp_path, api, events).run_once()

    assert events == ["identity"]
    assert api.closed is True


@pytest.mark.asyncio
async def test_invalid_configuration_does_not_expose_token(
    tmp_path: Path,
) -> None:
    invalid_token = "private-token"

    def load_invalid_settings() -> WorkerSettings:
        return WorkerSettings(
            swarm_api_url="http://control-plane.test",
            swarm_agent_token=invalid_token,
            swarm_workspace_root=tmp_path,
        )

    service = WorkerService(settings_loader=load_invalid_settings)

    with pytest.raises(WorkerConfigurationError) as raised:
        await service.run_once()

    assert invalid_token not in str(raised.value)


@pytest.mark.asyncio
async def test_task_start_conflict_is_lease_lost_without_fail(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events, start_error=ConflictError("expired"))

    outcome = await make_service(tmp_path, api, events).run_once()

    assert isinstance(outcome, LeaseLostOutcome)
    assert outcome.phase == "start"
    assert events[-1] == "start"
    assert not api.requests["fail"]
    assert not api.requests["complete"]


@pytest.mark.asyncio
async def test_lease_lost_during_execution_never_mutates_stale_task(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    partial = make_execution_result(success=False)
    service = make_service(
        tmp_path,
        api,
        events,
        executor_error=LeaseLost(partial),
    )

    outcome = await service.run_once()

    assert isinstance(outcome, LeaseLostOutcome)
    assert outcome.phase == "execution"
    assert events[-1] == "execute"
    assert not api.requests["fail"]
    assert not api.requests["complete"]


@pytest.mark.asyncio
async def test_fail_conflict_becomes_lease_lost_without_retry(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events, fail_error=ConflictError("expired"))
    service = make_service(
        tmp_path,
        api,
        events,
        execution_result=make_execution_result(success=False),
    )

    outcome = await service.run_once()

    assert isinstance(outcome, LeaseLostOutcome)
    assert outcome.phase == "fail"
    assert events.count("fail") == 1
    assert events.count("complete") == 0


@pytest.mark.asyncio
async def test_complete_conflict_is_not_retried_or_failed(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events, complete_error=ConflictError("expired"))

    outcome = await make_service(tmp_path, api, events).run_once()

    assert isinstance(outcome, LeaseLostOutcome)
    assert outcome.phase == "complete"
    assert events.count("complete") == 1
    assert events.count("fail") == 0


@pytest.mark.asyncio
async def test_workspace_setup_failure_releases_without_start(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    workspace_error = RuntimeError(f"setup rejected {AGENT_TOKEN} {LEASE_TOKEN}")

    outcome = await make_service(
        tmp_path,
        api,
        events,
        workspace_error=workspace_error,
    ).run_once()

    assert isinstance(outcome, ReleasedOutcome)
    assert events[-2:] == ["prepare", "release"]
    assert "RuntimeError" in outcome.reason_category
    serialized = outcome.model_dump_json()
    assert AGENT_TOKEN not in serialized
    assert LEASE_TOKEN not in serialized
    assert not api.requests["fail"]


@pytest.mark.asyncio
async def test_task_heartbeat_uses_real_lease_token(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    service = make_service(
        tmp_path,
        api,
        events,
        invoke_heartbeat=True,
    )

    outcome = await service.run_once()

    assert isinstance(outcome, SucceededOutcome)
    assert events.index("task_heartbeat") > events.index("execute")
    request = api.requests["heartbeat_task"][0]
    assert request.lease_token == LEASE_TOKEN


class CancellingExecutor(FakeExecutor):
    async def execute(self, **kwargs: object) -> WorkflowExecutionResult:
        self.events.append("execute")
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_cancellation_releases_and_propagates(tmp_path: Path) -> None:
    events: list[str] = []
    api = FakeAPI(events)
    settings = make_settings(tmp_path)
    workspace = make_workspace(tmp_path)
    manager = FakeWorkspaceManager(events, workspace)
    cancelling_executor = CancellingExecutor(events, make_execution_result())

    def validate(*args: object, **kwargs: object) -> ValidatedTaskPolicy:
        events.append("validate")
        return make_validated_policy()

    service = WorkerService(
        settings_loader=lambda: settings,
        api_client_factory=lambda current: api,
        workflow_loader_factory=lambda current: object(),
        workspace_manager_factory=lambda current: manager,
        executor_factory=lambda current: cancelling_executor,
        policy_validator=validate,
        role_package_loader=lambda current: verified_role_package(),
    )
    run = asyncio.create_task(service.run_once())
    while "execute" not in events:
        await asyncio.sleep(0)
    run.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run

    assert events[-1] == "release"
    assert api.closed is True
