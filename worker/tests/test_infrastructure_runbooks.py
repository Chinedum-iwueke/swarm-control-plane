from pathlib import Path

import pytest
from pydantic import ValidationError

from swarm_worker.infrastructure.runbooks import InfrastructureRunbook, load_runbook
from swarm_worker.models import InfrastructureContract

ROOT = Path(__file__).parents[1]


def test_reviewed_runbooks_load_without_commands() -> None:
    observer = load_runbook(ROOT / "infrastructure-runbooks/observer.yaml")
    restart = load_runbook(ROOT / "infrastructure-runbooks/controlled-restart.yaml")
    assert observer.operations[0].risk_level == 0
    assert restart.operations[0].risk_level == 3
    assert restart.operations[0].approval_required is True
    assert "command" not in observer.model_dump_json()
    assert "command" not in restart.model_dump_json()


def test_unknown_runbook_fields_and_arbitrary_parameters_are_rejected() -> None:
    with pytest.raises(ValidationError):
        InfrastructureRunbook.model_validate(
            {
                "schema_version": 1,
                "name": "vm2-infrastructure",
                "version": "1.0.0",
                "operations": [],
                "shell": "docker restart",
            }
        )
    with pytest.raises(ValidationError):
        InfrastructureContract.model_validate(
            {
                "runbook": "vm2-infrastructure",
                "runbook_version": "1.0.0",
                "operation": "restart-control-plane-api",
                "target": "vm2-control-plane",
                "parameters": {"service": "postgres"},
            }
        )
