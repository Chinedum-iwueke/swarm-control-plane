from __future__ import annotations

from typing import Any

import httpx


class ChannelError(RuntimeError):
    """Credential-free founder-channel failure."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        method: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.method = method
        self.status_code = status_code


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

    async def active_conversation(self, founder_key: str) -> dict[str, Any] | None:
        try:
            return await self._request(
                "GET",
                "/v1/founder-channel/conversations/active",
                params={"founder_key": founder_key},
            )
        except ChannelNotFound:
            return None

    async def conversations(self, founder_key: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/v1/founder-channel/conversations",
            params={"founder_key": founder_key},
        )

    async def create_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/founder-channel/conversations", json=payload
        )

    async def add_conversation_turn(
        self, conversation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/founder-channel/conversations/{conversation_id}/turns",
            json=payload,
        )

    async def transition_conversation(
        self, conversation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/founder-channel/conversations/{conversation_id}/transitions",
            json=payload,
        )

    async def tasks(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/tasks")

    async def proposals(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/proposals")

    async def approvals(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/approvals")

    async def alpha_mandates(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/alpha-mandates")

    async def notifications(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/notifications")

    async def acknowledge_notification(
        self, notification_id: str, delivery_reference: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/founder-channel/notifications/{notification_id}/acknowledge",
            json={"delivery_reference": delivery_reference},
        )

    async def missions(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/missions")

    async def research_cycles(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/v1/founder-channel/research-cycles")

    async def operational_notes(self, query: str | None = None) -> list[dict[str, Any]]:
        params = {"query": query} if query else None
        return await self._request(
            "GET", "/v1/founder-channel/operational-notes", params=params
        )

    async def approve_mission(self, mission_id: str, reason: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/founder-channel/missions/{mission_id}/approve",
            json={"reason": reason, "expires_in_seconds": 900},
        )

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

    async def approve_alpha_mandate(
        self, mandate_id: str, expected_digest: str, reason: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/founder-channel/alpha-mandates/{mandate_id}/approve",
            json={
                "reason": reason,
                "expected_digest": expected_digest,
                "expires_in_seconds": 900,
            },
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise ChannelError(
                "Control plane is unavailable.", retryable=True, method=method
            ) from exc
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
        error_type = ChannelNotFound if response.status_code == 404 else ChannelError
        raise error_type(
            f"Control plane returned HTTP {response.status_code}: {detail}",
            retryable=response.status_code == 429 or response.status_code >= 500,
            method=method,
            status_code=response.status_code,
        )


class ChannelNotFound(ChannelError):
    """Requested founder-channel resource does not exist."""
