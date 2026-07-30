import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from swarm_worker.workspace import (
    InvalidBaseRef,
    InvalidRepository,
    SubprocessRunner,
    TaskWorkspace,
    UnsafeCleanup,
    WorkspaceCollision,
    WorkspaceManager,
)

TASK_ID = UUID("22222222-2222-4222-8222-222222222222")


def git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


@pytest.fixture
def repository_root(tmp_path: Path) -> Path:
    root = tmp_path / "repositories"
    root.mkdir()
    repository = root / "project"
    repository.mkdir()
    git("init", "-b", "main", cwd=repository)
    git("config", "user.name", "Worker Tests", cwd=repository)
    git("config", "user.email", "worker@example.test", cwd=repository)
    (repository / "tracked.txt").write_text("primary checkout\n")
    git("add", "tracked.txt", cwd=repository)
    git("commit", "-m", "Initial commit", cwd=repository)
    return root


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    return tmp_path / "workspaces"


@pytest.fixture
def manager(
    repository_root: Path,
    workspace_root: Path,
) -> WorkspaceManager:
    return WorkspaceManager(repository_root, workspace_root)


def prepare(manager: WorkspaceManager) -> TaskWorkspace:
    workspace = manager.prepare(
        task_id=TASK_ID,
        task_number="TASK/unsafe 42",
        attempt_number=1,
        repository="project",
        base_ref="main",
    )
    assert isinstance(workspace, TaskWorkspace)
    return workspace


def test_valid_worktree_creation_and_layout(
    manager: WorkspaceManager,
    repository_root: Path,
    workspace_root: Path,
) -> None:
    primary_head = git("rev-parse", "HEAD", cwd=repository_root / "project")
    workspace = prepare(manager)

    assert workspace.repository.is_dir()
    assert workspace.logs.is_dir()
    assert workspace.artifacts.is_dir()
    assert workspace.plan.metadata_path.is_file()
    assert workspace.plan.attempt_directory.name == "attempt-1"
    assert workspace.plan.attempt_directory.parent.name.startswith("TASK-unsafe-42-")
    assert workspace.metadata.resolved_base_commit == primary_head
    assert git("rev-parse", "HEAD", cwd=workspace.repository) == primary_head
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=workspace.repository) == "HEAD"
    assert stat.S_IMODE(workspace.plan.metadata_path.stat().st_mode) == 0o600

    metadata = json.loads(workspace.plan.metadata_path.read_text())
    assert metadata["task_id"] == str(TASK_ID)
    assert metadata["repository"] == "project"
    assert metadata["base_ref"] == "main"


def test_primary_checkout_remains_unchanged(
    manager: WorkspaceManager,
    repository_root: Path,
) -> None:
    repository = repository_root / "project"
    head_before = git("rev-parse", "HEAD", cwd=repository)
    status_before = git("status", "--porcelain", cwd=repository)
    workspace = prepare(manager)
    (workspace.repository / "tracked.txt").write_text("workspace change\n")

    assert (repository / "tracked.txt").read_text() == "primary checkout\n"
    assert git("rev-parse", "HEAD", cwd=repository) == head_before
    assert git("status", "--porcelain", cwd=repository) == status_before


@pytest.mark.parametrize(
    "repository",
    ["../project", "nested/project", r"nested\\project", "..project", ".hidden"],
)
def test_repository_traversal_is_rejected(
    manager: WorkspaceManager,
    repository: str,
) -> None:
    with pytest.raises(InvalidRepository):
        manager.validate_preparation(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository=repository,
            base_ref="main",
        )


def test_symlink_escape_is_rejected(
    repository_root: Path,
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository_root / "escape").symlink_to(outside)

    with pytest.raises(InvalidRepository, match="outside"):
        WorkspaceManager(repository_root, workspace_root).validate_preparation(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository="escape",
            base_ref="main",
        )


def test_non_git_directory_is_rejected(
    repository_root: Path,
    workspace_root: Path,
) -> None:
    (repository_root / "plain").mkdir()

    with pytest.raises(InvalidRepository, match="not a Git"):
        WorkspaceManager(repository_root, workspace_root).validate_preparation(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository="plain",
            base_ref="main",
        )


def test_nonempty_workspace_collision_is_rejected(
    manager: WorkspaceManager,
) -> None:
    plan = manager.validate_preparation(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        base_ref="main",
    )
    plan.attempt_directory.mkdir(parents=True)
    (plan.attempt_directory / "foreign.txt").write_text("not worker metadata")

    with pytest.raises(WorkspaceCollision):
        manager.prepare(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository="project",
            base_ref="main",
        )


def test_cleanup_refuses_path_outside_workspace_root(
    manager: WorkspaceManager,
    tmp_path: Path,
) -> None:
    workspace = prepare(manager)
    outside = tmp_path / "outside"
    outside.mkdir()
    unsafe_plan = workspace.plan.__class__(
        **{
            **workspace.plan.__dict__,
            "attempt_directory": outside,
            "workspace_repository": outside / "repository",
            "metadata_path": outside / "metadata.json",
        }
    )
    unsafe_workspace = TaskWorkspace(
        plan=unsafe_plan,
        metadata=workspace.metadata,
    )

    with pytest.raises(UnsafeCleanup):
        manager.cleanup(unsafe_workspace)
    assert outside.exists()


def test_explicit_cleanup_removes_worktree(
    manager: WorkspaceManager,
) -> None:
    workspace = prepare(manager)
    manager.cleanup(workspace)

    assert not workspace.plan.attempt_directory.exists()


def test_worker_token_is_not_in_child_environment(tmp_path: Path) -> None:
    token = "swarm_ag_secret_worker_token"
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "LANG": "C.UTF-8",
        "SWARM_AGENT_TOKEN": token,
    }
    runner = SubprocessRunner(environment=environment)
    result = runner.run(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('SWARM_AGENT_TOKEN', 'absent'))",
        ]
    )

    assert result.stdout.strip() == "absent"
    assert token not in runner.environment.values()


def test_runner_rejects_shell_command_strings() -> None:
    with pytest.raises(ValueError, match="argument arrays"):
        SubprocessRunner().run("git status")  # type: ignore[arg-type]


def test_runner_invokes_subprocess_with_argument_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(args: tuple[str, ...], **kwargs: object):
        assert isinstance(args, tuple)
        assert args == ("git", "status")
        assert "shell" not in kwargs
        return subprocess.CompletedProcess(args, 0, "clean\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = SubprocessRunner().run(["git", "status"])

    assert result.args == ("git", "status")


def test_invalid_base_ref_is_rejected(manager: WorkspaceManager) -> None:
    with pytest.raises(InvalidBaseRef):
        manager.validate_preparation(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository="project",
            base_ref="-main;rm",
        )


class FailingWorktreeRunner(SubprocessRunner):
    def run(
        self,
        args: list[str],
        **kwargs: object,
    ):
        if "add" in args:
            raise RuntimeError("simulated worktree failure")
        return super().run(args, **kwargs)


def test_failed_worktree_has_no_valid_metadata(
    repository_root: Path,
    workspace_root: Path,
) -> None:
    manager = WorkspaceManager(
        repository_root,
        workspace_root,
        runner=FailingWorktreeRunner(),
    )

    with pytest.raises(RuntimeError, match="simulated"):
        manager.prepare(
            task_id=TASK_ID,
            task_number="TASK-1",
            attempt_number=1,
            repository="project",
            base_ref="main",
        )

    assert not list(workspace_root.rglob("metadata.json"))


def test_validation_only_does_not_create_workspace(
    manager: WorkspaceManager,
    workspace_root: Path,
) -> None:
    plan = manager.prepare(
        task_id=TASK_ID,
        task_number="TASK-1",
        attempt_number=1,
        repository="project",
        base_ref="main",
        validation_only=True,
    )

    assert not isinstance(plan, TaskWorkspace)
    assert not workspace_root.exists()
