from __future__ import annotations

from typing import Any

import httpx


class TelegramError(RuntimeError):
    """Credential-free Telegram API failure."""


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{token}",
            timeout=60,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def updates(
        self, offset: int, timeout: int
    ) -> list[dict[str, Any]]:
        return await self._call(
            "getUpdates",
            {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
        )

    async def send(
        self,
        chat_id: int,
        text: str,
        *,
        button_text: str | None = None,
        button_url: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        if button_text and button_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": button_text, "url": button_url}]]
            }
        await self._call("sendMessage", payload)

    async def _call(
        self, method: str, payload: dict[str, Any] | None = None
    ) -> Any:
        try:
            response = await self._client.post(method, json=payload or {})
        except httpx.RequestError as exc:
            raise TelegramError("Telegram is unavailable.") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise TelegramError("Telegram returned an invalid response.") from exc
        if not response.is_success or not body.get("ok"):
            description = str(body.get("description", "request rejected"))
            raise TelegramError(
                description.replace(self._token, "[REDACTED]")[:500]
            )
        return body["result"]
