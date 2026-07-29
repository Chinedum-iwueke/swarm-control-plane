import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from swarm_worker.models import AgentIdentity, Task
from swarm_worker.workflows import WorkflowDefinition, WorkflowLoader

_SAFE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_WORKFLOW = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_BASE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class WorkerPolicyError(Exception):
    """Base class for task contract and worker policy failures."""


class UnsupportedTaskType(WorkerPolicyError):
    """The worker has no implementation for the task type."""


class RepositoryNotAllowed(WorkerPolicyError):
    """The workflow does not permit the requested repository."""


class MachineNotAllowed(WorkerPolicyError):
    """The task cannot run on this worker's machine."""


class CapabilityMismatch(WorkerPolicyError):
    """The agent does not provide every capability required by the task."""


class RiskCeilingExceeded(WorkerPolicyError):
    """The task risk exceeds the authenticated agent's ceiling."""


class InvalidTaskContract(WorkerPolicyError):
    """The task input contract is malformed or unsafe."""


class CodeValidationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(
        min_length=1,
        max_length=100,
        pattern=_SAFE_REPOSITORY.pattern,
    )
    workflow: str = Field(
        min_length=1,
        max_length=100,
        pattern=_SAFE_WORKFLOW.pattern,
    )
    base_ref: str = Field(min_length=1, max_length=255)

    @field_validator("base_ref")
    @classmethod
    def validate_base_ref(cls, base_ref: str) -> str:
        return validate_base_ref(base_ref)


class ValidatedTaskPolicy(BaseModel):
    contract: CodeValidationContract
    workflow: WorkflowDefinition


def validate_base_ref(base_ref: str) -> str:
    if base_ref.startswith("-"):
        raise ValueError("base_ref must not begin with '-'")
    if not _SAFE_BASE_REF.fullmatch(base_ref):
        raise ValueError("base_ref contains unsafe characters")
    if (
        ".." in base_ref
        or "//" in base_ref
        or "@{" in base_ref
        or base_ref.endswith(("/", ".", ".lock"))
    ):
        raise ValueError("base_ref is not a safe Git reference")
    return base_ref


def validate_task_policy(
    task: Task,
    identity: AgentIdentity,
    workflow_loader: WorkflowLoader,
    *,
    worker_machine: str,
) -> ValidatedTaskPolicy:
    if task.task_type != "code_validation":
        raise UnsupportedTaskType(f"Task type {task.task_type!r} is not supported.")

    contract = _parse_contract(task.input_contract)
    workflow = workflow_loader.load(contract.workflow)

    if workflow.task_type != task.task_type:
        raise UnsupportedTaskType("Workflow task type does not match the leased task.")
    if contract.repository not in workflow.allowed_repositories:
        raise RepositoryNotAllowed(
            f"Repository {contract.repository!r} is not allowed by the workflow."
        )
    if task.allowed_machines and worker_machine not in task.allowed_machines:
        raise MachineNotAllowed(f"Task is not allowed on machine {worker_machine!r}.")

    missing_capabilities = sorted(
        set(task.required_capabilities) - set(identity.capabilities)
    )
    if missing_capabilities:
        raise CapabilityMismatch(
            "Agent is missing required capabilities: " + ", ".join(missing_capabilities)
        )
    if task.risk_level > identity.risk_ceiling:
        raise RiskCeilingExceeded(
            f"Task risk {task.risk_level} exceeds agent ceiling "
            f"{identity.risk_ceiling}."
        )

    return ValidatedTaskPolicy(contract=contract, workflow=workflow)


def _parse_contract(input_contract: dict[str, Any]) -> CodeValidationContract:
    try:
        return CodeValidationContract.model_validate(input_contract)
    except ValidationError as exc:
        summary = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise InvalidTaskContract(
            f"Task input contract failed validation: {summary}"
        ) from exc
