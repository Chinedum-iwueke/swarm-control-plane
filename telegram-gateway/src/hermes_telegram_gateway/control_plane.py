from __future__ import annotations

from typing import Any

import httpx


class ChannelError(RuntimeError):
    """Credential-free founder-channel failure."""


class FounderChannelClient:
    def __init__(
        self,
        api_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/v1/founder-channel/requests", json=payload)

    async def tasks(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/tasks")

    async def proposals(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/proposals")

    async def approvals(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/approvals")

    async def decide_proposal(
        self, proposal_id: str, action: str, reason: str
    ) -> dict[str, Any]:
        if action not in {"materialize", "reject"}:
            raise ValueError("Unsupported proposal action.")
        return await self._request(
            "POST",
            f"/v1/founder-channel/proposals/{proposal_id}/{action}",
            json={"reason": reason, "expires_in_seconds": 900},
        )

    async def decide_approval(
        self, approval_id: str, action: str, reason: str
    ) -> dict[str, Any]:
        if action not in {"approve", "reject"}:
            raise ValueError("Unsupported approval action.")
        return await self._request(
            "POST",
            f"/v1/founder-channel/approvals/{approval_id}/{action}",
            json={"reason": reason, "expires_in_seconds": 900},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise ChannelError("Control plane is unavailable.") from exc
        if response.is_success:
            return response.json()
        detail = "Request rejected."
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"][:500]
        except ValueError:
            pass
        detail = detail.replace(self._token, "[REDACTED]")
        raise ChannelError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )
