from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from swarm_worker.executors.code_validation import RootExecutionError
from swarm_worker.executors.research_experiment import ResearchExperimentExecutor
from swarm_worker.models import Task, WorkflowExecutionResult
from swarm_worker.policy import ResearchExperimentContract
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import (
    TaskWorkspace,
    WorkspaceMetadata,
    WorkspacePlan,
)

TASK_ID = UUID("88888888-8888-4888-8888-888888888888")
BASE_COMMIT = "b" * 40
NOW = "2026-07-30T12:00:00Z"


def contract(**changes: Any) -> ResearchExperimentContract:
    values = {
        "repository": "bulletproof_bt",
        "workflow": "research-experiment",
        "base_ref": "main",
        "program_id": "M8-SYNTHETIC-MOMENTUM",
        "hypothesis_id": "M8-H1-LAGGED-MOMENTUM",
        "hypothesis": "lagged-return-momentum",
        "dataset": "synthetic-regime-v1",
        "seed": 20260730,
        "observations": 1200,
        "train_fraction": 0.65,
        "transaction_cost_bps": 5.0,
        "acceptance": {
            "minimum_out_of_sample_sharpe": 1.0,
            "maximum_out_of_sample_drawdown": 0.25,
            "minimum_out_of_sample_trades": 50,
            "minimum_cost_stress_sharpe": 0.5,
        },
    }
    values.update(changes)
    return ResearchExperimentContract.model_validate(values)


def task(**changes: Any) -> Task:
    values = {
        "id": TASK_ID,
        "task_number": "M8-RESEARCH-1",
        "project": "bulletproof_bt",
        "task_type": "research_experiment",
        "title": "M8 research pilot",
        "objective": "Execute one predeclared synthetic hypothesis.",
        "status": "running",
        "priority": 65,
        "risk_level": 1,
        "assigned_agent_id": "11111111-1111-4111-8111-111111111111",
        "parent_task_id": None,
        "created_by": "founder-operator",
        "input_contract": contract().model_dump(mode="json"),
        "expected_outputs": [],
        "acceptance_criteria": [],
        "approval_policy": {},
        "required_capabilities": ["backtesting", "research-audit"],
        "allowed_machines": ["vm1-developer"],
        "max_attempts": 1,
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


def workflow() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "name": "research-experiment",
            "task_type": "research_experiment",
            "timeout_seconds": 1800,
            "allowed_repositories": ["bulletproof_bt"],
            "steps": [
                {
                    "name": "compile-python",
                    "command": ["python3", "-m", "compileall", "-q", "."],
                }
            ],
        }
    )


def workspace(tmp_path: Path, name: str) -> TaskWorkspace:
    attempt = tmp_path / name / "attempt-1"
    repository = attempt / "repository"
    logs = attempt / "logs"
    artifacts = attempt / "artifacts"
    repository.mkdir(parents=True)
    logs.mkdir(mode=0o700)
    artifacts.mkdir(mode=0o700)
    plan = WorkspacePlan(
        task_id=TASK_ID,
        task_number="M8-RESEARCH-1",
        attempt_number=1,
        repository="bulletproof_bt",
        source_repository=tmp_path / "source" / "bulletproof_bt",
        attempt_directory=attempt,
        workspace_repository=repository,
        logs_directory=logs,
        artifacts_directory=artifacts,
        metadata_path=attempt / "metadata.json",
        base_ref="main",
        resolved_base_commit=BASE_COMMIT,
    )
    metadata = WorkspaceMetadata(
        task_id=TASK_ID,
        task_number="M8-RESEARCH-1",
        attempt_number=1,
        repository="bulletproof_bt",
        source_repository=plan.source_repository,
        workspace_repository=repository,
        base_ref="main",
        resolved_base_commit=BASE_COMMIT,
        created_at=datetime.now(timezone.utc),
    )
    plan.metadata_path.write_text(metadata.model_dump_json(), encoding="utf-8")
    return TaskWorkspace(plan=plan, metadata=metadata)


class SuccessfulValidation:
    async def execute(self, *, task, workflow, workspace, heartbeat):
        await heartbeat(
            {
                "current_step": "compile-python",
                "completed_step_count": 1,
                "total_step_count": 1,
                "elapsed_seconds": 0.0,
            }
        )
        return WorkflowExecutionResult(
            workflow=workflow.name,
            repository="bulletproof_bt",
            base_commit=BASE_COMMIT,
            task_attempt=1,
            total_duration_seconds=0,
            steps=[],
            success=True,
        )


async def heartbeat(_: dict[str, object]) -> None:
    return None


@pytest.mark.asyncio
async def test_research_pilot_is_deterministic_and_accepted(tmp_path: Path) -> None:
    executor = ResearchExperimentExecutor(
        heartbeat_interval_seconds=1,
        validation_executor=SuccessfulValidation(),
        effective_uid=lambda: 1000,
    )
    first = await executor.execute(
        task=task(),
        workflow=workflow(),
        workspace=workspace(tmp_path, "first"),
        heartbeat=heartbeat,
    )
    second = await executor.execute(
        task=task(),
        workflow=workflow(),
        workspace=workspace(tmp_path, "second"),
        heartbeat=heartbeat,
    )
    assert first.success is True
    assert first.summary["verdict"] == "accepted"
    assert first.summary["production_eligible"] is False
    assert first.summary["audit_passed"] is True
    assert first.summary["evidence_sha256"] == second.summary["evidence_sha256"]
    assert first.summary["out_of_sample"]["annualized_sharpe"] == 6.24037808
    assert len(first.artifacts) == 3


@pytest.mark.asyncio
async def test_evidence_digest_and_artifact_permissions(tmp_path: Path) -> None:
    target = workspace(tmp_path, "permissions")
    executor = ResearchExperimentExecutor(
        heartbeat_interval_seconds=1,
        validation_executor=SuccessfulValidation(),
        effective_uid=lambda: 1000,
    )
    result = await executor.execute(
        task=task(),
        workflow=workflow(),
        workspace=target,
        heartbeat=heartbeat,
    )
    evidence = target.artifacts / "research-evidence.json"
    report = target.artifacts / "research-report.md"
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == result.summary[
        "evidence_sha256"
    ]
    assert evidence.stat().st_mode & 0o777 == 0o600
    assert report.stat().st_mode & 0o777 == 0o600
    assert "Production eligible:** no" in report.read_text(encoding="utf-8")
    document = json.loads(evidence.read_text(encoding="utf-8"))
    assert document["audit"]["selection_count"] == 1
    assert document["dataset"]["kind"] == "synthetic"


def test_contract_rejects_commands_unknown_fields_and_unsafe_variants() -> None:
    values = contract().model_dump()
    values["command"] = ["bash", "-c", "anything"]
    with pytest.raises(ValidationError):
        ResearchExperimentContract.model_validate(values)
    with pytest.raises(ValidationError):
        contract(repository="invariance_research")
    with pytest.raises(ValidationError):
        contract(dataset="live-market")
    with pytest.raises(ValidationError):
        contract(base_ref="-dangerous")


def test_rejected_hypothesis_is_still_a_valid_research_outcome() -> None:
    strict = contract(
        acceptance={
            "minimum_out_of_sample_sharpe": 9.0,
            "maximum_out_of_sample_drawdown": 0.01,
            "minimum_out_of_sample_trades": 500,
            "minimum_cost_stress_sharpe": 9.0,
        }
    )
    returns, _ = ResearchExperimentExecutor._generate_dataset(strict)
    split = int(len(returns) * strict.train_fraction)
    executor = ResearchExperimentExecutor(
        heartbeat_interval_seconds=1,
        effective_uid=lambda: 1000,
    )
    out_of_sample = executor._evaluate(
        returns[split - 1 :], strict.transaction_cost_bps, lag=1
    )
    audit = executor._audit(strict, returns, split, out_of_sample)
    assert audit["passed"] is True
    assert executor._accepted(strict, out_of_sample, audit) is False


@pytest.mark.asyncio
async def test_research_executor_refuses_root(tmp_path: Path) -> None:
    executor = ResearchExperimentExecutor(
        heartbeat_interval_seconds=1,
        validation_executor=SuccessfulValidation(),
        effective_uid=lambda: 0,
    )
    with pytest.raises(RootExecutionError):
        await executor.execute(
            task=task(),
            workflow=workflow(),
            workspace=workspace(tmp_path, "root"),
            heartbeat=heartbeat,
        )
