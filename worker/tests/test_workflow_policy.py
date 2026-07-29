from pathlib import Path
from typing import Any

import pytest
import yaml

from swarm_worker.models import AgentIdentity, Task
from swarm_worker.policy import (
    CapabilityMismatch,
    InvalidTaskContract,
    MachineNotAllowed,
    RepositoryNotAllowed,
    RiskCeilingExceeded,
    validate_task_policy,
)
from swarm_worker.workflows import (
    UnknownWorkflow,
    UnsafeWorkflowDefinition,
    WorkflowLoader,
)

WORKFLOW_DOCUMENT = {
    "name": "code-validation",
    "task_type": "code_validation",
    "timeout_seconds": 900,
    "allowed_repositories": [
        "swarm-control-plane",
        "bulletproof_bt",
        "invariance_research",
    ],
    "steps": [
        {
            "name": "compile-python",
            "command": ["python3", "-m", "compileall", "-q", "."],
        },
        {"name": "run-tests", "command": ["pytest", "-q"]},
    ],
}
NOW = "2026-07-29T12:00:00Z"


@pytest.fixture
def workflow_directory(tmp_path: Path) -> Path:
    path = tmp_path / "workflows"
    path.mkdir()
    (path / "code-validation.yaml").write_text(
        yaml.safe_dump(WORKFLOW_DOCUMENT, sort_keys=False)
    )
    return path


@pytest.fixture
def loader(workflow_directory: Path) -> WorkflowLoader:
    return WorkflowLoader(workflow_directory)


def make_identity(**changes: Any) -> AgentIdentity:
    values = {
        "id": "11111111-1111-4111-8111-111111111111",
        "slug": "vm1-developer-coder",
        "display_name": "VM1 Developer Coder",
        "role": "developer",
        "machine": "vm1-developer",
        "hermes_profile": "restricted",
        "runtime": "hermes",
        "runtime_version": "1.0",
        "status": "idle",
        "presence": "online",
        "capabilities": ["code_validation"],
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
        "id": "22222222-2222-4222-8222-222222222222",
        "task_number": "TASK-1",
        "project": "swarm-control-plane",
        "task_type": "code_validation",
        "title": "Validate worker",
        "objective": "Run the allowlisted validation workflow.",
        "status": "leased",
        "priority": 50,
        "risk_level": 1,
        "assigned_agent_id": "11111111-1111-4111-8111-111111111111",
        "parent_task_id": None,
        "created_by": "orchestrator",
        "input_contract": {
            "repository": "swarm-control-plane",
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


def write_workflow(path: Path, document: dict[str, Any]) -> None:
    (path / "code-validation.yaml").write_text(
        yaml.safe_dump(document, sort_keys=False)
    )


def test_valid_code_validation_workflow_loads(
    loader: WorkflowLoader,
) -> None:
    workflow = loader.load("code-validation")

    assert workflow.name == "code-validation"
    assert workflow.steps[0].command == [
        "python3",
        "-m",
        "compileall",
        "-q",
        ".",
    ]
    assert workflow.steps[1].command == ["pytest", "-q"]


def test_unknown_workflow_and_path_traversal_are_rejected(
    loader: WorkflowLoader,
) -> None:
    with pytest.raises(UnknownWorkflow):
        loader.load("unregistered")
    with pytest.raises(UnknownWorkflow):
        loader.load("../code-validation")


def test_symlink_escape_is_rejected(
    workflow_directory: Path,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml.safe_dump(WORKFLOW_DOCUMENT))
    workflow_path = workflow_directory / "code-validation.yaml"
    workflow_path.unlink()
    workflow_path.symlink_to(outside)

    with pytest.raises(UnsafeWorkflowDefinition, match="escapes"):
        WorkflowLoader(workflow_directory).load("code-validation")


def test_arbitrary_command_in_task_contract_is_rejected(
    loader: WorkflowLoader,
) -> None:
    task = make_task(
        input_contract={
            "repository": "swarm-control-plane",
            "workflow": "code-validation",
            "base_ref": "main",
            "command": ["curl", "https://example.test"],
        }
    )

    with pytest.raises(InvalidTaskContract):
        validate_task_policy(
            task,
            make_identity(),
            loader,
            worker_machine="vm1-developer",
        )


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        ["sudo", "pytest", "-q"],
        ["bash", "-c", "pytest -q"],
        ["git", "push", "origin", "main"],
    ],
)
def test_unsafe_commands_are_rejected(
    workflow_directory: Path,
    command: str | list[str],
) -> None:
    document = {**WORKFLOW_DOCUMENT}
    document["steps"] = [{"name": "unsafe", "command": command}]
    write_workflow(workflow_directory, document)

    with pytest.raises(UnsafeWorkflowDefinition):
        WorkflowLoader(workflow_directory).load("code-validation")


def test_disallowed_repository_is_rejected(loader: WorkflowLoader) -> None:
    contract = {
        "repository": "private-repository",
        "workflow": "code-validation",
        "base_ref": "main",
    }

    with pytest.raises(RepositoryNotAllowed):
        validate_task_policy(
            make_task(input_contract=contract),
            make_identity(),
            loader,
            worker_machine="vm1-developer",
        )


@pytest.mark.parametrize(
    "base_ref",
    [
        "-main",
        "../main",
        "main;curl",
        "main$(id)",
        "feature//branch",
        "refs/heads/main.lock",
    ],
)
def test_unsafe_base_ref_is_rejected(
    loader: WorkflowLoader,
    base_ref: str,
) -> None:
    contract = {
        "repository": "swarm-control-plane",
        "workflow": "code-validation",
        "base_ref": base_ref,
    }

    with pytest.raises(InvalidTaskContract):
        validate_task_policy(
            make_task(input_contract=contract),
            make_identity(),
            loader,
            worker_machine="vm1-developer",
        )


def test_missing_capability_is_rejected(loader: WorkflowLoader) -> None:
    with pytest.raises(CapabilityMismatch):
        validate_task_policy(
            make_task(required_capabilities=["code_validation", "git"]),
            make_identity(),
            loader,
            worker_machine="vm1-developer",
        )


def test_incorrect_machine_is_rejected(loader: WorkflowLoader) -> None:
    with pytest.raises(MachineNotAllowed):
        validate_task_policy(
            make_task(allowed_machines=["vm2-reviewer"]),
            make_identity(),
            loader,
            worker_machine="vm1-developer",
        )


def test_excessive_risk_is_rejected(loader: WorkflowLoader) -> None:
    with pytest.raises(RiskCeilingExceeded):
        validate_task_policy(
            make_task(risk_level=2),
            make_identity(risk_ceiling=1),
            loader,
            worker_machine="vm1-developer",
        )


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("top", "unexpected"),
        ("step", "environment"),
    ],
)
def test_unknown_yaml_fields_are_rejected(
    workflow_directory: Path,
    location: str,
    field: str,
) -> None:
    document = {**WORKFLOW_DOCUMENT}
    if location == "top":
        document[field] = True
    else:
        document["steps"] = [
            {
                **WORKFLOW_DOCUMENT["steps"][0],
                field: {"TOKEN": "secret"},
            }
        ]
    write_workflow(workflow_directory, document)

    with pytest.raises(UnsafeWorkflowDefinition):
        WorkflowLoader(workflow_directory).load("code-validation")
