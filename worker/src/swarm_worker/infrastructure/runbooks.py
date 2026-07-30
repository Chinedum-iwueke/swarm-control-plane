from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class OperationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal[
        "observe-control-plane",
        "restart-control-plane-api",
        "preflight-invariance-postgres",
    ]
    task_type: Literal["infrastructure_observation", "infrastructure_operation"]
    target: Literal["vm2-control-plane", "vm2-invariance-postgres"]
    risk_level: int = Field(ge=0, le=3)
    approval_required: bool
    evidence: list[str] = Field(min_length=1, max_length=20)


class InfrastructureRunbook(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    name: Literal["vm2-infrastructure", "vm2-postgres-deployment"]
    version: Literal["1.0.0"]
    operations: list[OperationDefinition] = Field(min_length=1, max_length=10)


class RunbookError(Exception):
    """A local infrastructure runbook is unavailable or invalid."""


def load_runbook(path: Path) -> InfrastructureRunbook:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return InfrastructureRunbook.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise RunbookError("Infrastructure runbook is invalid.") from exc
