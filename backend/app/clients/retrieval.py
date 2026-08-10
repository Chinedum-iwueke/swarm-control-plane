from __future__ import annotations

from types import TracebackType
from typing import Self

import httpx

from app.schemas.ingestion import CoordinateReplayResponse
from app.schemas.retrieval import (
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    ProjectionBuildResponse,
    ProjectionStatusResponse,
)


class RetrievalClientError(RuntimeError):
    pass


class CanonicalRetrievalClient:
    """Typed async client for the authenticated canonical retrieval API."""

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
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rebuild(self) -> ProjectionBuildResponse:
        return ProjectionBuildResponse.model_validate(
            await self._request("POST", "/v1/research/retrieval/projections/rebuild")
        )

    async def status(self) -> ProjectionStatusResponse:
        return ProjectionStatusResponse.model_validate(
            await self._request("GET", "/v1/research/retrieval/projections/status")
        )

    async def search(
        self, request: HybridRetrievalRequest
    ) -> HybridRetrievalResponse:
        return HybridRetrievalResponse.model_validate(
            await self._request(
                "POST",
                "/v1/research/retrieval/query",
                json=request.model_dump(mode="json"),
            )
        )

    async def replay(self, object_id: str) -> CoordinateReplayResponse:
        return CoordinateReplayResponse.model_validate(
            await self._request(
                "GET", f"/v1/research/retrieval/objects/{object_id}/replay"
            )
        )

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise RetrievalClientError(
                f"Retrieval request failed: {type(exc).__name__}"
            ) from exc
        if response.is_error:
            detail = response.reason_phrase
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("detail"), str):
                    detail = body["detail"]
            except ValueError:
                pass
            detail = detail.replace(self._token, "[REDACTED]")
            raise RetrievalClientError(
                f"Retrieval API returned HTTP {response.status_code}: {detail}"
            )
        return response.json()
