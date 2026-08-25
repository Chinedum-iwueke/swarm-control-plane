from __future__ import annotations

from typing import Any

import httpx


class TelegramError(RuntimeError):
    """Credential-free Telegram API failure."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        method: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.method = method
        self.status_code = status_code


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

    async def updates(self, offset: int, timeout: int) -> list[dict[str, Any]]:
        return await self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "edited_message"],
            },
        )

    async def send(
        self,
        chat_id: int,
        text: str,
        *,
        button_text: str | None = None,
        button_url: str | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        chunks = split_message(text)
        for index, chunk in enumerate(chunks):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if index == len(chunks) - 1 and button_text and button_url:
                payload["reply_markup"] = {
                    "inline_keyboard": [[{"text": button_text, "url": button_url}]]
                }
            result = await self._call("sendMessage", payload)
            if isinstance(result, dict):
                results.append(result)
        return results

    async def _call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.post(method, json=payload or {})
        except httpx.RequestError as exc:
            raise TelegramError(
                "Telegram is unavailable.", retryable=True, method=method
            ) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise TelegramError(
                "Telegram returned an invalid response.",
                retryable=response.status_code >= 500,
                method=method,
                status_code=response.status_code,
            ) from exc
        if not response.is_success or not body.get("ok"):
            description = str(body.get("description", "request rejected"))
            status_code = body.get("error_code", response.status_code)
            if not isinstance(status_code, int):
                status_code = response.status_code
            raise TelegramError(
                description.replace(self._token, "[REDACTED]")[:500],
                retryable=status_code == 429 or status_code >= 500,
                method=method,
                status_code=status_code,
            )
        return body["result"]


def split_message(text: str, limit: int = 4000) -> list[str]:
    if limit < 1:
        raise ValueError("Telegram message limit must be positive.")
    remaining = text or " "
    chunks: list[str] = []
    while len(remaining) > limit:
        boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary < 1:
            boundary = limit
        elif remaining[boundary].isspace():
            boundary += 1
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
    chunks.append(remaining)
    return chunks
