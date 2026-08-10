from __future__ import annotations

from typing import Any, Self
from uuid import UUID

import httpx


class CorpusOperationsError(RuntimeError):
    """A bounded corpus-operations error with credentials redacted."""


class CorpusOperationsClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self, project: str) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/research/corpus/health", params={"project": project}
        )

    async def create_backup(
        self, project: str, created_by: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/research/corpus/backups",
            json={"project": project, "created_by": created_by},
        )

    async def restore_backup(
        self, backup_id: UUID, requested_by: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/research/corpus/backups/{backup_id}/restore",
            json={
                "confirmation": "RESTORE_EMPTY_CORPUS",
                "requested_by": requested_by,
            },
        )

    async def recover_projections(
        self, project: str, requested_by: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/research/corpus/projections/recover",
            json={"project": project, "requested_by": requested_by},
        )

    async def recover_queue(
        self, project: str, requested_by: str, stale_after_seconds: int = 900
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/research/corpus/queue/recover",
            json={
                "project": project,
                "requested_by": requested_by,
                "stale_after_seconds": stale_after_seconds,
            },
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            raise CorpusOperationsError(
                "Corpus operations service is unavailable."
            ) from exc
        if response.is_success:
            return response.json()
        detail = response.text[:1000].replace(self._token, "[REDACTED]")
        raise CorpusOperationsError(
            f"Corpus operations returned HTTP {response.status_code}: {detail}"
        )
