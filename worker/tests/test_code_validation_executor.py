import asyncio
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from swarm_worker.api_client import ConflictError, ConnectionError
from swarm_worker.executors.code_validation import (
    AsyncProcessRunner,
    CodeValidationExecutor,
    LeaseLost,
    RootExecutionError,
)
from swarm_worker.models import Task
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import (
    TaskWorkspace,
    WorkspaceMetadata,
    WorkspacePlan,
)

TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
BASE_COMMIT = "a" * 40
NOW = "2026-07-29T12:00:00Z"


def make_task(**changes: Any) -> Task:
    values = {
        "id": TASK_ID,
        "task_number": "TASK-1",
        "project": "swarm-control-plane",
        "task_type": "code_validation",
        "title": "Validate code",
        "objective": "Run the server-local validation workflow.",
        "status": "running",
        "priority": 50,
        "risk_level": 1,
        "assigned_agent_id": "11111111-1111-4111-8111-111111111111",
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
        "started_at": NOW,
        "completed_at": None,
    }
    values.update(changes)
    return Task.model_validate(values)


def make_workflow(
    *commands: tuple[str, list[str]],
    timeout_seconds: int = 10,
    task_type: str = "code_validation",
) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "name": "code-validation",
            "task_type": task_type,
            "timeout_seconds": timeout_seconds,
            "allowed_repositories": ["project"],
            "steps": [{"name": name, "command": command} for name, command in commands],
        }
    )


def make_workspace(tmp_path: Path) -> TaskWorkspace:
    attempt = tmp_path / "TASK-1-id" / "attempt-1"
    repository = attempt / "repository"
    logs = attempt / "logs"
    artifacts = attempt / "artifacts"
    repository.mkdir(parents=True)
    logs.mkdir(mode=0o700)
    artifacts.mkdir(mode=0o700)
    metadata_path = attempt / "metadata.json"
    plan = WorkspacePlan(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        source_repository=tmp_path / "source" / "project",
        attempt_directory=attempt,
        workspace_repository=repository,
        logs_directory=logs,
        artifacts_directory=artifacts,
        metadata_path=metadata_path,
        base_ref="main",
        resolved_base_commit=BASE_COMMIT,
    )
    metadata = WorkspaceMetadata(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        source_repository=plan.source_repository,
        workspace_repository=repository,
        base_ref="main",
        resolved_base_commit=BASE_COMMIT,
        created_at=datetime.now(timezone.utc),
    )
    metadata_path.write_text(metadata.model_dump_json())
    return TaskWorkspace(plan=plan, metadata=metadata)


async def heartbeat_ok(progress: dict[str, object]) -> None:
    assert "current_step" in progress


def executor(**changes: Any) -> CodeValidationExecutor:
    values = {
        "step_timeout_seconds": 5.0,
        "heartbeat_interval_seconds": 0.05,
        "termination_grace_seconds": 0.2,
        "effective_uid": lambda: 1000,
    }
    values.update(changes)
    return CodeValidationExecutor(**values)


@pytest.mark.asyncio
async def test_successful_compile_and_test_workflow(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "module.py").write_text("VALUE = 42\n")
    (workspace.repository / "test_module.py").write_text(
        "from module import VALUE\n\ndef test_value():\n    assert VALUE == 42\n"
    )
    workflow = make_workflow(
        ("compile-python", ["python3", "-m", "compileall", "-q", "."]),
        ("run-tests", ["pytest", "-q"]),
    )

    result = await executor().execute(
        task=make_task(),
        workflow=workflow,
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is True
    assert [step.return_code for step in result.steps] == [0, 0]
    assert all(step.duration_seconds >= 0 for step in result.steps)
    assert result.base_commit == BASE_COMMIT
    assert result.task_attempt == 1


@pytest.mark.asyncio
async def test_engineering_mission_can_reuse_named_validation_workflow(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    task = make_task(task_type="engineering_mission")
    workflow = make_workflow(
        ("compile-python", ["python3", "-m", "compileall", "-q", "."]),
        task_type="engineering_mission",
    )

    result = await executor().execute(
        task=task,
        workflow=workflow,
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_first_failure_stops_later_steps(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_failure.py").write_text(
        "def test_failure():\n    assert False\n"
    )
    workflow = make_workflow(
        ("run-tests", ["pytest", "-q"]),
        ("compile-python", ["python3", "-m", "compileall", "-q", "."]),
    )

    result = await executor().execute(
        task=make_task(),
        workflow=workflow,
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is False
    assert result.termination_reason == "step_failed"
    assert len(result.steps) == 1
    assert result.steps[0].return_code != 0
    assert not (workspace.logs / "compile-python.stdout.log").exists()


@pytest.mark.asyncio
async def test_timeout_terminates_process_and_records_result(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(30)\n"
    )
    workflow = make_workflow(("run-tests", ["pytest", "-q"]))

    result = await executor(step_timeout_seconds=0.2).execute(
        task=make_task(),
        workflow=workflow,
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is False
    assert result.termination_reason == "step_timeout"
    assert result.steps[0].timed_out is True
    assert result.steps[0].return_code is not None
    assert result.total_duration_seconds < 3


@pytest.mark.asyncio
async def test_overall_workflow_timeout_terminates_step(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(30)\n"
    )

    result = await executor(step_timeout_seconds=10).execute(
        task=make_task(),
        workflow=make_workflow(
            ("run-tests", ["pytest", "-q"]),
            timeout_seconds=1,
        ),
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is False
    assert result.termination_reason == "workflow_timeout"
    assert result.steps[0].timed_out is True
    assert result.total_duration_seconds < 3


@pytest.mark.asyncio
async def test_timeout_terminates_child_process_group(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    child_code = (
        "import pathlib, signal, sys, time;"
        "signal.signal(signal.SIGTERM, "
        "lambda *_: (pathlib.Path('child-terminated').write_text('yes'), "
        "sys.exit(0)));"
        "pathlib.Path('child-started').write_text('yes');"
        "time.sleep(30)"
    )
    test_code = f"""
        import subprocess
        import sys
        import time

        def test_child_group():
            subprocess.Popen([sys.executable, "-c", {child_code!r}])
            while not __import__("pathlib").Path("child-started").exists():
                time.sleep(0.01)
            time.sleep(30)
    """
    (workspace.repository / "test_child.py").write_text(textwrap.dedent(test_code))

    result = await executor(step_timeout_seconds=2.0).execute(
        task=make_task(),
        workflow=make_workflow(("run-tests", ["pytest", "-q"])),
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )
    await asyncio.sleep(0.1)

    assert result.steps[0].timed_out is True
    assert (workspace.repository / "child-started").read_text() == "yes"
    assert (workspace.repository / "child-terminated").read_text() == "yes"


@pytest.mark.asyncio
async def test_logs_written_and_api_result_bounded(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_output.py").write_text(
        "def test_output():\n    print('x' * 1_000_000)\n    assert False\n"
    )

    result = await executor().execute(
        task=make_task(),
        workflow=make_workflow(("run-tests", ["pytest", "-q"])),
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    stdout_log = workspace.plan.attempt_directory / result.steps[0].stdout_log
    stderr_log = workspace.plan.attempt_directory / result.steps[0].stderr_log
    assert stdout_log.stat().st_size > 1_000_000
    assert stderr_log.exists()
    assert len(result.model_dump_json()) < 10_000
    assert result.steps[0].stdout_log == "logs/run-tests.stdout.log"


@pytest.mark.asyncio
async def test_token_not_inherited_and_working_directory_is_worktree(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    token = "swarm_ag_do_not_inherit_this_token"
    (workspace.repository / "test_environment.py").write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "def test_environment():\n"
        "    assert 'SWARM_AGENT_TOKEN' not in os.environ\n"
        "    assert '/primary-checkout' not in os.environ['PYTHONPATH']\n"
        "    assert os.environ['PYTHONPATH'].split(os.pathsep)[0] == os.getcwd()\n"
        "    assert os.environ['PATH'].split(os.pathsep)[0] == "
        "str(Path(sys.executable).resolve().parent)\n"
        "    assert os.environ['VIRTUAL_ENV'] == "
        "str(Path(sys.executable).resolve().parent.parent)\n"
        "    assert os.environ['APP_ENVIRONMENT'] == 'test'\n"
        "    secret_path = Path(os.environ['POSTGRES_PASSWORD_FILE'])\n"
        "    assert secret_path.read_text() == 'isolated-worker-test-value'\n"
        "    assert oct(secret_path.stat().st_mode & 0o777) == '0o600'\n"
        "    Path('observed-cwd').write_text(os.getcwd())\n"
    )
    runner = AsyncProcessRunner(
        environment={
            **os.environ,
            "SWARM_AGENT_TOKEN": token,
            "PYTHONPATH": "/primary-checkout",
        }
    )

    result = await executor(process_runner=runner).execute(
        task=make_task(),
        workflow=make_workflow(("run-tests", ["pytest", "-q"])),
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is True
    assert (workspace.repository / "observed-cwd").read_text() == str(
        workspace.repository
    )
    assert token not in runner.environment.values()


@pytest.mark.asyncio
async def test_periodic_heartbeat_and_temporary_failure_recorded(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(0.3)\n"
    )
    calls: list[dict[str, object]] = []

    async def heartbeat(progress: dict[str, object]) -> None:
        calls.append(progress)
        if len(calls) == 1:
            raise ConnectionError("temporary")

    result = await executor().execute(
        task=make_task(),
        workflow=make_workflow(("run-tests", ["pytest", "-q"])),
        workspace=workspace,
        heartbeat=heartbeat,
    )

    assert result.success is True
    assert len(calls) >= 2
    assert calls[-1]["current_step"] == "run-tests"
    assert calls[-1]["completed_step_count"] == 0
    assert calls[-1]["total_step_count"] == 1
    assert float(calls[-1]["elapsed_seconds"]) >= 0
    assert result.heartbeat_failures == ["run-tests: temporary ConnectionError"]


@pytest.mark.asyncio
async def test_lease_loss_terminates_execution(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    (workspace.repository / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(30)\n"
    )

    async def lease_lost(progress: dict[str, object]) -> None:
        raise ConflictError("lease expired")

    with pytest.raises(LeaseLost) as raised:
        await executor().execute(
            task=make_task(),
            workflow=make_workflow(("run-tests", ["pytest", "-q"])),
            workspace=workspace,
            heartbeat=lease_lost,
        )

    assert raised.value.result.success is False
    assert raised.value.result.termination_reason == "lease_lost"
    assert raised.value.result.steps[0].return_code is not None
    assert raised.value.result.total_duration_seconds < 3


@pytest.mark.asyncio
async def test_arbitrary_task_command_cannot_influence_execution(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    marker = workspace.repository / "arbitrary-command-ran"
    task = make_task(
        input_contract={
            "repository": "project",
            "workflow": "code-validation",
            "base_ref": "main",
            "command": ["touch", str(marker)],
        }
    )
    (workspace.repository / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n"
    )

    result = await executor().execute(
        task=task,
        workflow=make_workflow(("run-tests", ["pytest", "-q"])),
        workspace=workspace,
        heartbeat=heartbeat_ok,
    )

    assert result.success is True
    assert not marker.exists()


@pytest.mark.asyncio
async def test_root_execution_is_rejected(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(RootExecutionError):
        await CodeValidationExecutor(effective_uid=lambda: 0).execute(
            task=make_task(),
            workflow=make_workflow(("run-tests", ["pytest", "-q"])),
            workspace=workspace,
            heartbeat=heartbeat_ok,
        )
