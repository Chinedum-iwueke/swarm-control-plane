from __future__ import annotations

from typing import Any

import httpx

from swarm_worker.supervisor.config import SupervisorSettings


class SupervisorError(RuntimeError):
    """Credential-free supervisor failure."""


class SupervisorAuthenticationError(SupervisorError):
    pass


class MissionSupervisor:
    def __init__(
        self,
        settings: SupervisorSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = settings.swarm_mission_supervisor_token
        self._client = httpx.AsyncClient(
            base_url=settings.normalized_api_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def reconcile(self) -> list[dict[str, Any]]:
        try:
            response = await self._client.post("/v1/supervisor/reconcile")
        except httpx.RequestError as exc:
            raise SupervisorError("Control plane is unavailable.") from exc
        if response.status_code in {401, 403}:
            raise SupervisorAuthenticationError(
                "Mission supervisor authentication failed."
            )
        if not response.is_success:
            raise SupervisorError(
                f"Control plane returned HTTP {response.status_code}."
            )
        value = response.json()
        if not isinstance(value, list):
            raise SupervisorError("Control plane returned an invalid response.")
        return value
