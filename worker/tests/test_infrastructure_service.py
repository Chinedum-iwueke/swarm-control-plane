import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from swarm_worker.api_client import ConflictError
from swarm_worker.infrastructure.config import InfrastructureSettings
from swarm_worker.infrastructure.runbooks import OperationDefinition
from swarm_worker.infrastructure.service import InfrastructureService
from swarm_worker.models import (
    AgentIdentity,
    BrokerExecutionResult,
    BrokerTicketPayload,
    BrokerTicketResponse,
    LeaseResponse,
    Task,
)

ROOT = Path("/home/omenka/Projects/swarm-control-plane/worker")
AGENT_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("22222222-2222-4222-8222-222222222222")
LEASE_TOKEN = "lease-token-for-infrastructure-tests"


def settings(tmp_path: Path) -> InfrastructureSettings:
    return InfrastructureSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token="agent-token-for-infrastructure-tests",
        swarm_task_heartbeat_seconds=0.001,
        swarm_infrastructure_workspace_root=tmp_path / "workspaces",
        swarm_infrastructure_role_manifest=(
            ROOT / "role-packages/vm2-infrastructure-operator/manifest.yaml"
        ),
        swarm_infrastructure_runbook_directory=ROOT / "infrastructure-runbooks",
        swarm_source_commit="a" * 40,
    )


def identity(**changes: Any) -> AgentIdentity:
    now = datetime.now(UTC)
    values = {
        "id": AGENT_ID,
        "slug": "vm2-infrastructure-operator",
        "display_name": "VM2 Infrastructure Operator",
        "role": "infrastructure",
        "machine": "vm2-deployment",
        "hermes_profile": "restricted",
        "runtime": None,
        "runtime_version": None,
        "status": "idle",
        "presence": "online",
        "capabilities": [
            "infrastructure-observation",
            "service-health",
            "controlled-restart",
        ],
        "heartbeat_metadata": {},
        "risk_ceiling": 3,
        "is_enabled": True,
        "last_heartbeat_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(changes)
    return AgentIdentity.model_validate(values)


def task(**changes: Any) -> Task:
    now = datetime.now(UTC)
    values = {
        "id": TASK_ID,
        "task_number": "VM2-INFRA-1",
        "project": "swarm-control-plane",
        "task_type": "infrastructure_observation",
        "title": "Observe infrastructure",
        "objective": "Collect bounded health evidence.",
        "status": "leased",
        "priority": 50,
        "risk_level": 0,
        "assigned_agent_id": AGENT_ID,
        "parent_task_id": None,
        "created_by": "founder-operator",
        "input_contract": {
            "runbook": "vm2-infrastructure",
            "runbook_version": "1.0.0",
            "operation": "observe-control-plane",
            "target": "vm2-control-plane",
            "parameters": {},
        },
        "expected_outputs": [],
        "acceptance_criteria": [],
        "approval_policy": {},
        "required_capabilities": ["infrastructure-observation"],
        "allowed_machines": ["vm2-deployment"],
        "max_attempts": 1,
        "attempt_count": 1,
        "leased_at": now,
        "lease_expires_at": now + timedelta(minutes=5),
        "last_execution_heartbeat_at": None,
        "result": {},
        "failure": {},
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
    }
    values.update(changes)
    return Task.model_validate(values)


def ticket(value: Task) -> BrokerTicketResponse:
    now = datetime.now(UTC)
    return BrokerTicketResponse(
        payload=BrokerTicketPayload(
            schema_version=1,
            task_id=value.id,
            task_number=value.task_number,
            attempt_number=value.attempt_count,
            agent_id=AGENT_ID,
            machine="vm2-deployment",
            task_type=value.task_type,
            risk_level=value.risk_level,
            plan_digest="b" * 64,
            contract=value.input_contract,
            nonce="c" * 64,
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
        signature="d" * 64,
    )


class FakeAPI:
    def __init__(
        self,
        events: list[str],
        leased_task: Task | None,
        *,
        heartbeat_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.leased_task = leased_task
        self.heartbeat_error = heartbeat_error
        self.complete_calls = 0
        self.fail_calls = 0
        self.release_calls = 0

    async def get_identity(self):
        self.events.append("identity")
        return identity()

    async def send_agent_heartbeat(self, request):
        self.events.append("agent_heartbeat")
        return object()

    async def lease_task(self, request):
        self.events.append("lease")
        if self.leased_task is None:
            return LeaseResponse(task=None, lease_token=None)
        return LeaseResponse(task=self.leased_task, lease_token=LEASE_TOKEN)

    async def start_task(self, task_id, request):
        self.events.append("start")
        return object()

    async def get_broker_ticket(self, task_id, request):
        self.events.append("ticket")
        return ticket(self.leased_task)

    async def heartbeat_task(self, task_id, request):
        self.events.append("task_heartbeat")
        if self.heartbeat_error:
            raise self.heartbeat_error
        return object()

    async def register_artifact(self, task_id, request):
        self.events.append("artifact")
        return object()

    async def complete_task(self, task_id, request):
        self.events.append("complete")
        self.complete_calls += 1
        return object()

    async def fail_task(self, task_id, request):
        self.events.append("fail")
        self.fail_calls += 1
        return object()

    async def release_task(self, task_id, request):
        self.events.append("release")
        self.release_calls += 1
        return object()

    async def aclose(self):
        self.events.append("close")


class FakeBroker:
    def __init__(self, events: list[str], leased_task: Task) -> None:
        self.events = events
        self.leased_task = leased_task
        self.cancelled = False

    async def execute(self, broker_ticket):
        self.events.append("broker")
        try:
            await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        now = datetime.now(UTC)
        return BrokerExecutionResult(
            success=True,
            operation=broker_ticket.payload.contract.operation,
            task_id=self.leased_task.id,
            attempt_number=1,
            started_at=now,
            ended_at=now,
            pre_state={"healthy": True, "latest_backup": None},
        )


@pytest.mark.asyncio
async def test_observation_lifecycle_and_evidence(tmp_path: Path) -> None:
    events: list[str] = []
    leased_task = task()
    api = FakeAPI(events, leased_task)
    broker = FakeBroker(events, leased_task)
    service = InfrastructureService(
        settings(tmp_path),
        api_factory=lambda _: api,
        broker_factory=lambda _: broker,
    )

    outcome = await service.run_once()

    assert outcome.status == "succeeded"
    assert api.complete_calls == 1
    assert api.fail_calls == 0
    assert events[:5] == ["identity", "agent_heartbeat", "lease", "start", "ticket"]
    assert "task_heartbeat" in events
    assert events.index("artifact") < events.index("complete")
    evidence = list((tmp_path / "workspaces").rglob("infrastructure-evidence.json"))
    assert len(evidence) == 1


@pytest.mark.asyncio
async def test_policy_rejection_releases_before_start(tmp_path: Path) -> None:
    events: list[str] = []
    api = FakeAPI(events, task(allowed_machines=["somewhere-else"]))
    service = InfrastructureService(
        settings(tmp_path),
        api_factory=lambda _: api,
        broker_factory=lambda _: pytest.fail("broker must not be created"),
    )

    outcome = await service.run_once()

    assert outcome.status == "released"
    assert events == ["identity", "agent_heartbeat", "lease", "release", "close"]
    assert api.release_calls == 1


@pytest.mark.asyncio
async def test_lease_loss_cancels_client_and_never_completes(tmp_path: Path) -> None:
    events: list[str] = []
    leased_task = task()
    api = FakeAPI(
        events,
        leased_task,
        heartbeat_error=ConflictError("lease no longer owned"),
    )
    broker = FakeBroker(events, leased_task)
    service = InfrastructureService(
        settings(tmp_path),
        api_factory=lambda _: api,
        broker_factory=lambda _: broker,
    )

    outcome = await service.run_once()

    assert outcome.status == "lease_lost"
    assert broker.cancelled is True
    assert api.complete_calls == 0
    assert api.fail_calls == 0


@pytest.mark.asyncio
async def test_no_work_does_not_create_broker(tmp_path: Path) -> None:
    events: list[str] = []
    api = FakeAPI(events, None)
    service = InfrastructureService(
        settings(tmp_path),
        api_factory=lambda _: api,
        broker_factory=lambda _: pytest.fail("broker must not be created"),
    )

    outcome = await service.run_once()

    assert outcome.status == "no_work"
    assert events == ["identity", "agent_heartbeat", "lease", "close"]


@pytest.mark.parametrize(
    ("operation", "task_type", "risk"),
    [
        ("start-invariance-postgres-private", "infrastructure_operation", 3),
        ("initialize-invariance-schema", "infrastructure_operation", 3),
        ("configure-invariance-backups", "infrastructure_operation", 3),
        ("verify-invariance-postgres", "infrastructure_observation", 0),
        ("prepare-invariance-cutover", "infrastructure_observation", 0),
    ],
)
def test_deployment_phases_match_closed_service_policy(
    operation: str,
    task_type: str,
    risk: int,
) -> None:
    leased_task = task(
        project="invariance_research",
        task_type=task_type,
        risk_level=risk,
        input_contract={
            "runbook": "vm2-postgres-deployment",
            "runbook_version": "1.0.0",
            "operation": operation,
            "target": "vm2-invariance-postgres",
            "parameters": {},
        },
    )
    definition = OperationDefinition(
        name=operation,
        task_type=task_type,
        target="vm2-invariance-postgres",
        risk_level=risk,
        approval_required=risk >= 2,
        evidence=["bounded evidence"],
    )
    manifest = SimpleNamespace(
        task_types=["infrastructure_observation", "infrastructure_operation"]
    )

    contract = InfrastructureService._validate_task(
        leased_task,
        manifest,
        {operation: definition},
        identity(),
    )

    assert contract.operation == operation
