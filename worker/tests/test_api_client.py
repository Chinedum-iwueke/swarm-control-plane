from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import pytest

from swarm_worker.api_client import (
    AuthenticationError,
    ConflictError,
    ServerError,
    SwarmAPIClient,
    ValidationError,
)
from swarm_worker.config import WorkerSettings
from swarm_worker.models import (
    AgentHeartbeat,
    TaskCompleteRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskStartRequest,
)

AGENT_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "22222222-2222-4222-8222-222222222222"
TOKEN = "swarm_ag_abcdef_secure-agent-token"
LEASE_TOKEN = "swarm_lt_abcdef_secure-lease-token"
NOW = "2026-07-29T12:00:00Z"


def settings() -> WorkerSettings:
    return WorkerSettings(
        swarm_api_url="http://control-plane.test///",
        swarm_agent_token=TOKEN,
    )


def identity_json() -> dict[str, Any]:
    return {
        "id": AGENT_ID,
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


def task_json(*, status: str = "leased") -> dict[str, Any]:
    return {
        "id": TASK_ID,
        "task_number": "TASK-1",
        "project": "swarm-control-plane",
        "task_type": "code_validation",
        "title": "Validate worker",
        "objective": "Run the allowlisted validation workflow.",
        "status": status,
        "priority": 50,
        "risk_level": 1,
        "assigned_agent_id": AGENT_ID if status in {"leased", "running"} else None,
        "parent_task_id": None,
        "created_by": "orchestrator",
        "input_contract": {"repository": "swarm-control-plane"},
        "expected_outputs": [],
        "acceptance_criteria": [],
        "approval_policy": {},
        "required_capabilities": ["code_validation"],
        "allowed_machines": ["vm1-developer"],
        "max_attempts": 3,
        "attempt_count": 1,
        "leased_at": NOW if status in {"leased", "running"} else None,
        "lease_expires_at": NOW if status in {"leased", "running"} else None,
        "last_execution_heartbeat_at": (
            NOW if status in {"leased", "running"} else None
        ),
        "result": {},
        "failure": {},
        "created_at": NOW,
        "updated_at": NOW,
        "started_at": NOW if status == "running" else None,
        "completed_at": None,
    }


def mutation_json(*, status: str, event_type: str) -> dict[str, Any]:
    return {
        "task": task_json(status=status),
        "event": {
            "id": 1,
            "task_id": TASK_ID,
            "agent_id": AGENT_ID,
            "event_type": event_type,
            "attempt_number": 1,
            "message": "accepted",
            "payload": {},
            "created_at": NOW,
        },
    }


@pytest.mark.asyncio
async def test_bearer_header_and_identity_are_parsed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert str(request.url) == "http://control-plane.test/v1/agent/me"
        return httpx.Response(200, json=identity_json())

    async with SwarmAPIClient(
        settings(), transport=httpx.MockTransport(handler)
    ) as client:
        identity = await client.get_identity()

    assert identity.id == UUID(AGENT_ID)
    assert identity.created_at == datetime(
        2026,
        7,
        29,
        12,
        tzinfo=timezone.utc,
    )


@pytest.mark.asyncio
async def test_agent_heartbeat_body_and_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/agent/heartbeat"
        assert request.read()
        assert request.headers["content-type"] == "application/json"
        assert __import__("json").loads(request.content) == {
            "status": "busy",
            "runtime": "hermes",
            "runtime_version": "1.2.3",
            "capabilities": ["code_validation"],
            "metadata": {"machine": "vm1-developer"},
        }
        return httpx.Response(
            200,
            json={
                "agent_id": AGENT_ID,
                "status": "busy",
                "presence": "online",
                "received_at": NOW,
            },
        )

    heartbeat = AgentHeartbeat(
        status="busy",
        runtime_version="1.2.3",
        capabilities=["code_validation"],
        metadata={"machine": "vm1-developer"},
    )
    async with SwarmAPIClient(
        settings(), transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.send_agent_heartbeat(heartbeat)

    assert response.agent_id == UUID(AGENT_ID)
    assert response.status == "busy"


@pytest.mark.asyncio
async def test_lease_response_is_parsed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert __import__("json").loads(request.content) == {"lease_seconds": 300}
        return httpx.Response(
            200,
            json={"task": task_json(), "lease_token": LEASE_TOKEN},
        )

    async with SwarmAPIClient(
        settings(), transport=httpx.MockTransport(handler)
    ) as client:
        lease = await client.lease_task(TaskLeaseRequest())

    assert lease.task is not None
    assert lease.task.id == UUID(TASK_ID)
    assert lease.lease_token == LEASE_TOKEN


@pytest.mark.asyncio
async def test_no_task_response_is_not_an_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"task": None, "lease_token": None},
        )
    )
    async with SwarmAPIClient(settings(), transport=transport) as client:
        lease = await client.lease_task(TaskLeaseRequest())

    assert lease.task is None
    assert lease.lease_token is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (409, ConflictError),
        (422, ValidationError),
        (500, ServerError),
    ],
)
async def test_error_status_mapping_and_secret_redaction(
    status_code: int,
    exception_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            json={
                "detail": {
                    "agent": TOKEN,
                    "lease": LEASE_TOKEN,
                    "message": "request rejected",
                }
            },
        )
    )
    async with SwarmAPIClient(settings(), transport=transport) as client:
        with pytest.raises(exception_type) as raised:
            await client.start_task(
                TASK_ID,
                TaskStartRequest(lease_token=LEASE_TOKEN),
            )

    message = str(raised.value)
    assert "request rejected" in message
    assert TOKEN not in message
    assert LEASE_TOKEN not in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "request_model", "expected_body", "status", "event_type"),
    [
        (
            "start",
            TaskStartRequest(
                lease_token=LEASE_TOKEN,
                message="Starting validation.",
            ),
            {
                "lease_token": LEASE_TOKEN,
                "message": "Starting validation.",
            },
            "running",
            "task_started",
        ),
        (
            "complete",
            TaskCompleteRequest(
                lease_token=LEASE_TOKEN,
                message="Validation passed.",
                result={"return_codes": {"pytest": 0}},
            ),
            {
                "lease_token": LEASE_TOKEN,
                "message": "Validation passed.",
                "result": {"return_codes": {"pytest": 0}},
            },
            "succeeded",
            "task_completed",
        ),
        (
            "fail",
            TaskFailRequest(
                lease_token=LEASE_TOKEN,
                message="Validation failed.",
                failure={"step": "pytest"},
                retryable=True,
            ),
            {
                "lease_token": LEASE_TOKEN,
                "message": "Validation failed.",
                "failure": {"step": "pytest"},
                "retryable": True,
            },
            "failed",
            "task_failed",
        ),
    ],
)
async def test_lifecycle_request_bodies_match_schema(
    action: str,
    request_model: TaskStartRequest | TaskCompleteRequest | TaskFailRequest,
    expected_body: dict[str, Any],
    status: str,
    event_type: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/v1/agent/tasks/{TASK_ID}/{action}"
        assert __import__("json").loads(request.content) == expected_body
        return httpx.Response(
            200,
            json=mutation_json(status=status, event_type=event_type),
        )

    async with SwarmAPIClient(
        settings(), transport=httpx.MockTransport(handler)
    ) as client:
        method = getattr(client, f"{action}_task")
        response = await method(TASK_ID, request_model)

    assert response.event.event_type == event_type
