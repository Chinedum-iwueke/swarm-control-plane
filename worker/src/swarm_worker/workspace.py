from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from swarm_worker.policy import validate_base_ref

_SAFE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_TASK_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")
_ENVIRONMENT_ALLOWLIST = frozenset(
    {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV"}
)
_GIT_ENVIRONMENT = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}


class WorkspaceError(Exception):
    """Base class for isolated workspace failures."""


class InvalidRepository(WorkspaceError):
    """The requested source repository is unsafe or is not a Git repository."""


class InvalidBaseRef(WorkspaceError):
    """The requested Git base reference is unsafe or cannot be resolved."""


class WorkspaceCollision(WorkspaceError):
    """An existing workspace cannot be proven to belong to this attempt."""


class WorkspaceCommandError(WorkspaceError):
    """A subprocess required for workspace management failed."""

    def __init__(self, command: Sequence[str], return_code: int, stderr: str) -> None:
        executable = Path(command[0]).name if command else "command"
        detail = (stderr.strip() or "no error output")[:2000]
        super().__init__(
            f"{executable} failed with return code {return_code}: {detail}"
        )
        self.return_code = return_code


class UnsafeCleanup(WorkspaceError):
    """A cleanup target failed workspace ownership or containment checks."""


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str


class SubprocessRunner:
    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        source = os.environ if environment is None else environment
        self._environment = {
            key: source[key] for key in _ENVIRONMENT_ALLOWLIST if key in source
        }
        self._environment.update(_GIT_ENVIRONMENT)

    @property
    def environment(self) -> Mapping[str, str]:
        return dict(self._environment)

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 60.0,
        check: bool = True,
    ) -> CommandResult:
        if isinstance(args, (str, bytes)) or not args:
            raise ValueError("subprocess commands must be non-empty argument arrays")

        command = tuple(str(argument) for argument in args)
        environment = dict(self._environment)

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceCommandError(command, -1, type(exc).__name__) from exc

        result = CommandResult(
            args=command,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.return_code != 0:
            raise WorkspaceCommandError(
                result.args,
                result.return_code,
                result.stderr,
            )
        return result


class WorkspaceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    task_number: str
    attempt_number: int
    repository: str
    source_repository: Path
    workspace_repository: Path
    base_ref: str
    resolved_base_commit: str
    created_at: datetime


@dataclass(frozen=True)
class WorkspacePlan:
    task_id: UUID
    task_number: str
    attempt_number: int
    repository: str
    source_repository: Path
    attempt_directory: Path
    workspace_repository: Path
    logs_directory: Path
    artifacts_directory: Path
    metadata_path: Path
    base_ref: str
    resolved_base_commit: str


@dataclass(frozen=True)
class TaskWorkspace:
    plan: WorkspacePlan
    metadata: WorkspaceMetadata

    @property
    def repository(self) -> Path:
        return self.plan.workspace_repository

    @property
    def logs(self) -> Path:
        return self.plan.logs_directory

    @property
    def artifacts(self) -> Path:
        return self.plan.artifacts_directory


class WorkspaceManager:
    def __init__(
        self,
        repository_root: Path,
        workspace_root: Path,
        *,
        runner: SubprocessRunner | None = None,
        command_timeout_seconds: float = 60.0,
    ) -> None:
        self._repository_root = repository_root.resolve()
        self._workspace_root = workspace_root.resolve()
        self._runner = runner or SubprocessRunner()
        self._command_timeout_seconds = command_timeout_seconds

    def validate_preparation(
        self,
        *,
        task_id: UUID,
        task_number: str,
        attempt_number: int,
        repository: str,
        base_ref: str,
    ) -> WorkspacePlan:
        if attempt_number < 1:
            raise WorkspaceError("Attempt number must be positive.")

        source_repository = self._resolve_repository(repository)
        safe_base_ref = self._validate_base_ref(base_ref)
        resolved_base_commit = self._resolve_base_commit(
            source_repository,
            safe_base_ref,
        )
        attempt_directory = self._attempt_directory(
            task_id,
            task_number,
            attempt_number,
        )
        self._require_beneath_workspace_root(attempt_directory)

        return WorkspacePlan(
            task_id=task_id,
            task_number=task_number,
            attempt_number=attempt_number,
            repository=repository,
            source_repository=source_repository,
            attempt_directory=attempt_directory,
            workspace_repository=attempt_directory / "repository",
            logs_directory=attempt_directory / "logs",
            artifacts_directory=attempt_directory / "artifacts",
            metadata_path=attempt_directory / "metadata.json",
            base_ref=safe_base_ref,
            resolved_base_commit=resolved_base_commit,
        )

    def prepare(
        self,
        *,
        task_id: UUID,
        task_number: str,
        attempt_number: int,
        repository: str,
        base_ref: str,
        validation_only: bool = False,
    ) -> WorkspacePlan | TaskWorkspace:
        plan = self.validate_preparation(
            task_id=task_id,
            task_number=task_number,
            attempt_number=attempt_number,
            repository=repository,
            base_ref=base_ref,
        )
        if validation_only:
            return plan

        existing = self._load_existing(plan)
        if existing is not None:
            return existing

        self._create_directories(plan)
        try:
            self._run_git(
                plan.source_repository,
                [
                    "worktree",
                    "add",
                    "--detach",
                    "--",
                    str(plan.workspace_repository),
                    plan.resolved_base_commit,
                ],
            )
            plan.workspace_repository.chmod(0o700)
            metadata = self._metadata_for(plan)
            self._write_metadata(plan.metadata_path, metadata)
        except Exception:
            self._remove_incomplete_workspace(plan)
            raise

        return TaskWorkspace(plan=plan, metadata=metadata)

    def cleanup(self, workspace: TaskWorkspace) -> None:
        plan = workspace.plan
        self._require_beneath_workspace_root(plan.attempt_directory)
        self._require_beneath_workspace_root(plan.workspace_repository)
        metadata = self._read_metadata(plan.metadata_path)
        if metadata != workspace.metadata or not self._metadata_matches(plan, metadata):
            raise UnsafeCleanup("Workspace metadata does not prove ownership.")

        self._run_git(
            plan.source_repository,
            [
                "worktree",
                "remove",
                "--force",
                "--",
                str(plan.workspace_repository),
            ],
        )
        self._run_git(
            plan.source_repository,
            ["worktree", "prune"],
        )
        self._safe_rmtree(plan.attempt_directory)

        task_directory = plan.attempt_directory.parent
        if task_directory.exists() and not any(task_directory.iterdir()):
            task_directory.rmdir()

    def _resolve_repository(self, repository: str) -> Path:
        if (
            not _SAFE_REPOSITORY.fullmatch(repository)
            or repository.startswith(".")
            or "/" in repository
            or "\\" in repository
            or ".." in repository
        ):
            raise InvalidRepository("Repository name is unsafe.")

        candidate = self._repository_root / repository
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise InvalidRepository("Source repository does not exist.") from exc
        if (
            not resolved.is_dir()
            or resolved.parent != self._repository_root
            or not resolved.is_relative_to(self._repository_root)
        ):
            raise InvalidRepository(
                "Source repository resolves outside the repository root."
            )

        try:
            result = self._run_git(
                resolved,
                ["rev-parse", "--show-toplevel"],
            )
        except WorkspaceCommandError as exc:
            raise InvalidRepository(
                "Source directory is not a Git repository."
            ) from exc

        try:
            git_root = Path(result.stdout.strip()).resolve(strict=True)
        except OSError as exc:
            raise InvalidRepository("Git returned an invalid repository root.") from exc
        if git_root != resolved:
            raise InvalidRepository("Source directory must be the Git repository root.")
        return resolved

    @staticmethod
    def _validate_base_ref(base_ref: str) -> str:
        try:
            return validate_base_ref(base_ref)
        except ValueError as exc:
            raise InvalidBaseRef(str(exc)) from exc

    def _resolve_base_commit(
        self,
        source_repository: Path,
        base_ref: str,
    ) -> str:
        try:
            result = self._run_git(
                source_repository,
                ["rev-parse", "--verify", f"{base_ref}^{{commit}}"],
            )
        except WorkspaceCommandError as exc:
            raise InvalidBaseRef(
                f"Base ref {base_ref!r} does not resolve to a commit."
            ) from exc

        commit = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
            raise InvalidBaseRef("Git returned an invalid base commit.")
        return commit.lower()

    def _attempt_directory(
        self,
        task_id: UUID,
        task_number: str,
        attempt_number: int,
    ) -> Path:
        safe_number = _SAFE_TASK_COMPONENT.sub("-", task_number).strip(".-_")
        safe_number = safe_number[:80] or "task"
        task_directory = self._workspace_root / f"{safe_number}-{task_id}"
        return task_directory / f"attempt-{attempt_number}"

    def _load_existing(self, plan: WorkspacePlan) -> TaskWorkspace | None:
        if not plan.attempt_directory.exists():
            return None
        if not plan.attempt_directory.is_dir():
            raise WorkspaceCollision("Workspace path is not a directory.")
        if not any(plan.attempt_directory.iterdir()):
            return None
        if not plan.metadata_path.is_file():
            raise WorkspaceCollision("Non-empty workspace has no valid metadata.")

        try:
            metadata = self._read_metadata(plan.metadata_path)
        except WorkspaceError as exc:
            raise WorkspaceCollision("Existing workspace metadata is invalid.") from exc
        if not self._metadata_matches(plan, metadata):
            raise WorkspaceCollision(
                "Existing workspace belongs to another task attempt."
            )
        if not plan.workspace_repository.is_dir():
            raise WorkspaceCollision("Existing worktree repository is missing.")
        try:
            worktree_root = self._run_git(
                plan.workspace_repository,
                ["rev-parse", "--show-toplevel"],
            ).stdout.strip()
            worktree_head = self._run_git(
                plan.workspace_repository,
                ["rev-parse", "HEAD"],
            ).stdout.strip()
        except WorkspaceCommandError as exc:
            raise WorkspaceCollision(
                "Existing workspace is not a valid Git worktree."
            ) from exc
        if (
            Path(worktree_root).resolve() != plan.workspace_repository.resolve()
            or worktree_head.lower() != plan.resolved_base_commit
        ):
            raise WorkspaceCollision(
                "Existing worktree does not match recorded metadata."
            )
        return TaskWorkspace(plan=plan, metadata=metadata)

    def _create_directories(self, plan: WorkspacePlan) -> None:
        self._workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._workspace_root.chmod(0o700)
        task_directory = plan.attempt_directory.parent
        task_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        task_directory.chmod(0o700)
        plan.attempt_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        plan.attempt_directory.chmod(0o700)
        plan.logs_directory.mkdir(mode=0o700)
        plan.artifacts_directory.mkdir(mode=0o700)

    def _run_git(
        self,
        source_repository: Path,
        arguments: Sequence[str],
        *,
        check: bool = True,
    ) -> CommandResult:
        return self._runner.run(
            [
                "git",
                "-c",
                f"core.hooksPath={os.devnull}",
                "-C",
                str(source_repository),
                *arguments,
            ],
            timeout_seconds=self._command_timeout_seconds,
            check=check,
        )

    @staticmethod
    def _metadata_for(plan: WorkspacePlan) -> WorkspaceMetadata:
        return WorkspaceMetadata(
            task_id=plan.task_id,
            task_number=plan.task_number,
            attempt_number=plan.attempt_number,
            repository=plan.repository,
            source_repository=plan.source_repository,
            workspace_repository=plan.workspace_repository,
            base_ref=plan.base_ref,
            resolved_base_commit=plan.resolved_base_commit,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _write_metadata(path: Path, metadata: WorkspaceMetadata) -> None:
        content = (
            json.dumps(
                metadata.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w") as metadata_file:
            metadata_file.write(content)

    @staticmethod
    def _read_metadata(path: Path) -> WorkspaceMetadata:
        if path.is_symlink():
            raise WorkspaceError("Workspace metadata must not be a symlink.")
        try:
            return WorkspaceMetadata.model_validate_json(path.read_text())
        except (OSError, ValidationError) as exc:
            raise WorkspaceError("Workspace metadata is invalid.") from exc

    @staticmethod
    def _metadata_matches(
        plan: WorkspacePlan,
        metadata: WorkspaceMetadata,
    ) -> bool:
        return (
            metadata.task_id == plan.task_id
            and metadata.task_number == plan.task_number
            and metadata.attempt_number == plan.attempt_number
            and metadata.repository == plan.repository
            and metadata.source_repository == plan.source_repository
            and metadata.workspace_repository == plan.workspace_repository
            and metadata.base_ref == plan.base_ref
            and metadata.resolved_base_commit == plan.resolved_base_commit
        )

    def _remove_incomplete_workspace(self, plan: WorkspacePlan) -> None:
        if plan.workspace_repository.exists():
            self._run_git(
                plan.source_repository,
                [
                    "worktree",
                    "remove",
                    "--force",
                    "--",
                    str(plan.workspace_repository),
                ],
                check=False,
            )
        self._run_git(
            plan.source_repository,
            ["worktree", "prune"],
            check=False,
        )
        if plan.attempt_directory.exists():
            self._safe_rmtree(plan.attempt_directory)

    def _safe_rmtree(self, path: Path) -> None:
        self._require_beneath_workspace_root(path)
        shutil.rmtree(path)

    def _require_beneath_workspace_root(self, path: Path) -> None:
        resolved = path.resolve(strict=False)
        if resolved == self._workspace_root or not resolved.is_relative_to(
            self._workspace_root
        ):
            raise UnsafeCleanup("Path is not beneath the workspace root.")
