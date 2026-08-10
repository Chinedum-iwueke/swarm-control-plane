from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

import httpx

from app.schemas.memory import DossierReplayResponse, DossierResponse


class MemoryClientError(RuntimeError):
    pass


class InstitutionalMemoryClient:
    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = bearer_token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def list_dossiers(self) -> list[DossierResponse]:
        body = await self._request("GET", "/v1/research/memory/dossiers")
        return [DossierResponse.model_validate(item) for item in body]

    async def get_dossier(self, dossier_id: UUID) -> DossierResponse:
        return DossierResponse.model_validate(
            await self._request("GET", f"/v1/research/memory/dossiers/{dossier_id}")
        )

    async def replay_dossier(self, dossier_id: UUID) -> DossierReplayResponse:
        return DossierReplayResponse.model_validate(
            await self._request(
                "GET", f"/v1/research/memory/dossiers/{dossier_id}/replay"
            )
        )

    async def _request(self, method: str, path: str):
        try:
            response = await self._client.request(method, path)
        except httpx.RequestError as exc:
            raise MemoryClientError(
                f"Memory request failed: {type(exc).__name__}"
            ) from exc
        if response.is_error:
            detail = response.reason_phrase
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("detail"), str):
                    detail = body["detail"]
            except ValueError:
                pass
            raise MemoryClientError(
                f"Memory API returned HTTP {response.status_code}: "
                f"{detail.replace(self._token, '[REDACTED]')}"
            )
        return response.json()
