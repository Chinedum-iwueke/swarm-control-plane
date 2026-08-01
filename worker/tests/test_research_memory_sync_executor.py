from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from swarm_worker.config import WorkerSettings
from swarm_worker.executors.research_memory_sync import ResearchMemorySyncExecutor
from swarm_worker.models import (
    ResearchMemoryRegistrationResponse,
    Task,
)
from swarm_worker.research_memory_bridge import MemoryExport
from swarm_worker.workflows import WorkflowLoader
from swarm_worker.workspace import TaskWorkspace, WorkspaceMetadata, WorkspacePlan

TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
NOW = "2026-08-01T12:00:00Z"


def settings(tmp_path: Path) -> WorkerSettings:
    return WorkerSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token="swarm_ag_research_memory_test_token",
        swarm_repository_root=tmp_path / "repositories",
        swarm_workspace_root=tmp_path / "workspaces",
        swarm_workflow_directory=Path(__file__).parents[1] / "workflows",
        swarm_role_package_manifest=(
            Path(__file__).parents[1]
            / "role-packages/vm1-research-memory-steward/manifest.yaml"
        ),
        swarm_task_heartbeat_seconds=0.01,
    )


def task(**changes: Any) -> Task:
    values = {
        "id": TASK_ID,
        "task_number": "MEMORY-SYNC-1",
        "project": "bulletproof_bt",
        "task_type": "research_memory_sync",
        "title": "Sync research memory",
        "objective": "Register one bounded research-memory export.",
        "status": "running",
        "priority": 60,
        "risk_level": 0,
        "assigned_agent_id": "11111111-1111-4111-8111-111111111111",
        "parent_task_id": None,
        "created_by": "founder-mission-control",
        "input_contract": {
            "repository": "bulletproof_bt",
            "workflow": "research-memory-sync",
            "base_ref": "main",
        },
        "expected_outputs": [],
        "acceptance_criteria": [],
        "approval_policy": {},
        "required_capabilities": ["research-memory-sync"],
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


def workspace(tmp_path: Path) -> TaskWorkspace:
    attempt = tmp_path / "workspaces" / "MEMORY-SYNC-1" / "attempt-1"
    repository = attempt / "repository"
    logs = attempt / "logs"
    artifacts = attempt / "artifacts"
    repository.mkdir(parents=True)
    logs.mkdir(mode=0o700)
    artifacts.mkdir(mode=0o700)
    metadata_path = attempt / "metadata.json"
    plan = WorkspacePlan(
        task_id=TASK_ID,
        task_number="MEMORY-SYNC-1",
        attempt_number=1,
        repository="bulletproof_bt",
        source_repository=tmp_path / "repositories" / "bulletproof_bt",
        attempt_directory=attempt,
        workspace_repository=repository,
        logs_directory=logs,
        artifacts_directory=artifacts,
        metadata_path=metadata_path,
        base_ref="main",
        resolved_base_commit="a" * 40,
    )
    metadata = WorkspaceMetadata(
        task_id=TASK_ID,
        task_number="MEMORY-SYNC-1",
        attempt_number=1,
        repository="bulletproof_bt",
        source_repository=plan.source_repository,
        workspace_repository=repository,
        base_ref="main",
        resolved_base_commit="a" * 40,
        created_at=datetime.now(timezone.utc),
    )
    return TaskWorkspace(plan=plan, metadata=metadata)


@pytest.mark.asyncio
async def test_executor_registers_fixed_memory_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = MemoryExport(
        repository_commit="a" * 40,
        database_digest="b" * 64,
        counts={
            "trades": 10,
            "invalid_trades": 2,
            "state_buckets": 3,
            "candidates": 1,
            "recommendations": 4,
        },
        run_ids=["run-1"],
        hypothesis_ids=["hypothesis-1"],
        strongest_states=[],
        weakest_states=[],
        candidates=[],
        recommendations=[],
    )
    observed: dict[str, Any] = {}

    def fake_build(repository: Path, database: Path, **kwargs) -> MemoryExport:
        observed["repository"] = repository
        observed["database"] = database
        return document

    class FakeAPI:
        def __init__(self, _settings: WorkerSettings) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def register_research_memory(self, request):
            observed["request"] = request
            return ResearchMemoryRegistrationResponse(
                export={"id": "export-id"},
                document_key="bulletproof-memory-key",
                unchanged=False,
            )

    monkeypatch.setattr(
        "swarm_worker.executors.research_memory_sync.build_export", fake_build
    )
    monkeypatch.setattr(
        "swarm_worker.executors.research_memory_sync.SwarmAPIClient", FakeAPI
    )
    config = settings(tmp_path)
    prepared = workspace(tmp_path)
    result = await ResearchMemorySyncExecutor(config).execute(
        task=task(),
        workflow=WorkflowLoader(config.swarm_workflow_directory).load(
            "research-memory-sync"
        ),
        workspace=prepared,
        heartbeat=lambda _: None,
    )

    assert result.success is True
    assert observed["repository"] == config.swarm_repository_root / "bulletproof_bt"
    assert observed["database"] == (
        config.swarm_repository_root / "bulletproof_bt/research_db/research.sqlite"
    )
    assert result.summary["export_id"] == "export-id"
    assert result.summary["counts"]["invalid_trades"] == 2
    assert "SWARM_AGENT_TOKEN" not in result.model_dump_json()
    assert (prepared.logs / "sync-research-memory.stdout.log").is_file()
