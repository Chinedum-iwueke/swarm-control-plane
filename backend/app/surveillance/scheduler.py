from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx

from app.models.surveillance import SurveillanceSource
from app.schemas.surveillance import SourcePollCreate
from app.surveillance.connectors import FeedConnector


class SurveillanceScheduler:
    def __init__(
        self,
        connector: FeedConnector,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.25,
    ) -> None:
        self._connector = connector
        self._max_attempts = max_attempts
        self._base_delay = base_delay

    async def collect(
        self,
        source: SurveillanceSource,
        submit: Callable[[SourcePollCreate], Awaitable[object]],
        *,
        requested_by: str,
    ) -> object:
        status = 503
        entries = []
        for attempt in range(1, self._max_attempts + 1):
            try:
                status, entries = await self._connector.fetch(
                    source.feed_url, frozenset(source.allowed_hosts)
                )
                if status < 500:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                status = 503
            if attempt < self._max_attempts:
                await asyncio.sleep(self._base_delay * 2 ** (attempt - 1))
        return await submit(
            SourcePollCreate(
                requested_by=requested_by,
                entries=entries,
                connector_version=self._connector.version,
                fetched_at=datetime.now(UTC),
                http_status=status,
            )
        )
