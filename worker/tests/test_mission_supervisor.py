import httpx
import pytest

from swarm_worker.supervisor.config import SupervisorSettings
from swarm_worker.supervisor.service import (
    MissionSupervisor,
    SupervisorAuthenticationError,
)


def settings(token: str = "s" * 64) -> SupervisorSettings:
    return SupervisorSettings(
        swarm_api_url="http://control.test/",
        swarm_mission_supervisor_token=token,
    )


@pytest.mark.asyncio
async def test_reconcile_uses_bearer_and_parses_list() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {'s' * 64}"
        assert request.url.path == "/v1/supervisor/reconcile"
        return httpx.Response(200, json=[])

    service = MissionSupervisor(settings(), transport=httpx.MockTransport(handler))
    try:
        assert await service.reconcile() == []
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_authentication_error_never_contains_token() -> None:
    token = "private-supervisor-token-" + "x" * 40

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": token})

    service = MissionSupervisor(settings(token), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(SupervisorAuthenticationError) as captured:
            await service.reconcile()
        assert token not in str(captured.value)
    finally:
        await service.close()
