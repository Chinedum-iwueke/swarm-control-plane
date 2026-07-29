from __future__ import annotations

import re
from pathlib import Path, PurePath
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

WORKFLOW_FILES = {
    "code-validation": "code-validation.yaml",
    "code-validation-failure": "code-validation-failure.yaml",
}

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHELL_METACHARACTERS = frozenset("|;&`$><\n\r")
_DENIED_EXECUTABLES = frozenset(
    {
        "apt",
        "apt-get",
        "bash",
        "cat",
        "chmod",
        "chown",
        "curl",
        "dnf",
        "doas",
        "env",
        "eval",
        "firewall-cmd",
        "head",
        "iptables",
        "less",
        "more",
        "mount",
        "mv",
        "nc",
        "netcat",
        "nft",
        "npm",
        "pip",
        "pip3",
        "rm",
        "service",
        "sh",
        "source",
        "su",
        "sudo",
        "systemctl",
        "tail",
        "tee",
        "umount",
        "wget",
        "yum",
        "zsh",
    }
)
_READ_ONLY_GIT_OPTIONS = {
    "branch": frozenset({"--list"}),
    "diff": frozenset(
        {"--exit-code", "--name-only", "--name-status", "--quiet", "--stat"}
    ),
    "log": frozenset({"--no-decorate", "--oneline"}),
    "rev-parse": frozenset(
        {
            "--git-dir",
            "--is-inside-work-tree",
            "--show-prefix",
            "--show-toplevel",
        }
    ),
    "show": frozenset({"--no-patch", "--stat", "--summary"}),
    "status": frozenset(
        {
            "--branch",
            "--porcelain",
            "--short",
            "--untracked-files=all",
            "--untracked-files=no",
            "--untracked-files=normal",
        }
    ),
}
_ALLOWED_PYTHON_FLAGS = frozenset({"-q"})
_ALLOWED_PYTEST_OPTIONS = frozenset({"-q", "--quiet"})


class WorkflowPolicyError(Exception):
    """Base class for workflow loading and definition failures."""


class UnknownWorkflow(WorkflowPolicyError):
    """The task requested a workflow that is not allowlisted."""


class UnsafeWorkflowDefinition(WorkflowPolicyError):
    """An allowlisted workflow failed schema or command policy validation."""


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, pattern=_SAFE_NAME.pattern)
    command: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=4096)]],
        Field(min_length=1, max_length=64),
    ]

    @field_validator("command")
    @classmethod
    def validate_command(cls, command: list[str]) -> list[str]:
        if any(not argument for argument in command):
            raise ValueError("command arguments must not be empty")

        executable = command[0]
        if (
            Path(executable).is_absolute()
            or "/" in executable
            or "\\" in executable
            or _has_path_traversal(executable)
        ):
            raise ValueError("executable must be an approved bare name")
        if executable in _DENIED_EXECUTABLES:
            raise ValueError(f"executable {executable!r} is forbidden")
        if any(_contains_shell_metacharacters(argument) for argument in command):
            raise ValueError("shell metacharacters are forbidden")
        if any(_has_path_traversal(argument) for argument in command):
            raise ValueError("path traversal is forbidden")

        if executable in {"python", "python3"}:
            _validate_python(command)
        elif executable == "pytest":
            _validate_pytest(command)
        elif executable == "git":
            _validate_git(command)
        else:
            raise ValueError(f"executable {executable!r} is not allowlisted")

        return command


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, pattern=_SAFE_NAME.pattern)
    task_type: Literal["code_validation"]
    timeout_seconds: int = Field(ge=1, le=3600)
    allowed_repositories: Annotated[
        list[
            Annotated[
                str,
                Field(min_length=1, max_length=100, pattern=_SAFE_NAME.pattern),
            ]
        ],
        Field(min_length=1),
    ]
    steps: Annotated[list[WorkflowStep], Field(min_length=1, max_length=50)]

    @field_validator("allowed_repositories")
    @classmethod
    def unique_repositories(cls, repositories: list[str]) -> list[str]:
        if len(repositories) != len(set(repositories)):
            raise ValueError("allowed repositories must be unique")
        return repositories


class WorkflowLoader:
    def __init__(self, workflow_directory: Path) -> None:
        self._directory = workflow_directory.resolve()

    def load(self, workflow_name: str) -> WorkflowDefinition:
        filename = WORKFLOW_FILES.get(workflow_name)
        if filename is None:
            raise UnknownWorkflow(f"Workflow {workflow_name!r} is not allowlisted.")

        workflow_path = (self._directory / filename).resolve()
        if not workflow_path.is_relative_to(self._directory):
            raise UnsafeWorkflowDefinition(
                "Allowlisted workflow path escapes the workflow directory."
            )

        try:
            document: Any = yaml.safe_load(workflow_path.read_text())
        except (OSError, yaml.YAMLError) as exc:
            raise UnsafeWorkflowDefinition(
                f"Unable to load workflow {workflow_name!r}."
            ) from exc

        if not isinstance(document, dict):
            raise UnsafeWorkflowDefinition(
                f"Workflow {workflow_name!r} must contain a YAML mapping."
            )

        try:
            workflow = WorkflowDefinition.model_validate(document)
        except ValidationError as exc:
            raise UnsafeWorkflowDefinition(
                f"Workflow {workflow_name!r} failed policy validation: "
                f"{_validation_summary(exc)}"
            ) from exc

        if workflow.name != workflow_name:
            raise UnsafeWorkflowDefinition(
                "Workflow name does not match its allowlisted name."
            )
        return workflow


def _contains_shell_metacharacters(argument: str) -> bool:
    return any(character in argument for character in _SHELL_METACHARACTERS)


def _has_path_traversal(argument: str) -> bool:
    return ".." in PurePath(argument).parts


def _validation_summary(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors(include_input=False, include_url=False)
    )


def _validate_python(command: list[str]) -> None:
    if len(command) < 3 or command[1:3] != ["-m", "compileall"]:
        raise ValueError("python is restricted to the compileall module")
    if any(
        argument.startswith("-") and argument not in _ALLOWED_PYTHON_FLAGS
        for argument in command[3:]
    ):
        raise ValueError("unsupported compileall option")
    _reject_absolute_operands(command[3:])


def _validate_pytest(command: list[str]) -> None:
    if any(
        argument.startswith("-") and argument not in _ALLOWED_PYTEST_OPTIONS
        for argument in command[1:]
    ):
        raise ValueError("unsupported pytest option")
    _reject_absolute_operands(command[1:])


def _validate_git(command: list[str]) -> None:
    if len(command) < 2:
        raise ValueError("git requires an allowlisted subcommand")

    subcommand = command[1]
    if subcommand in _READ_ONLY_GIT_OPTIONS:
        options = _READ_ONLY_GIT_OPTIONS[subcommand]
        if any(
            argument.startswith("-") and argument not in options
            for argument in command[2:]
        ):
            raise ValueError(f"unsupported git {subcommand} option")
        if subcommand == "branch" and (len(command) < 3 or command[2] != "--list"):
            raise ValueError("git branch is restricted to listing branches")
        _reject_absolute_operands(command[2:])
        return

    raise ValueError(f"git subcommand {subcommand!r} is not allowlisted")


def _reject_absolute_operands(arguments: list[str]) -> None:
    if any(
        not argument.startswith("-") and Path(argument).is_absolute()
        for argument in arguments
    ):
        raise ValueError("absolute command operands are not allowed")
