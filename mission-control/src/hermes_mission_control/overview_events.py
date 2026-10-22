"""Bounded, local-only overview change notifications for Mission Control."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

EVENT_SCHEMA_VERSION = "mission-control-overview-event-v1"
_CLOSE = object()


@dataclass(frozen=True)
class OverviewEvent:
    event_id: int
    event: str
    data: dict[str, Any]


@dataclass
class OverviewSubscription:
    replay: list[OverviewEvent]
    queue: asyncio.Queue[OverviewEvent | object]
    cursor_state: str | None = None


class SubscriberLimitExceeded(RuntimeError):
    pass


class OverviewEventBroker:
    """One bounded upstream poller fan-outs small, non-secret events to browsers."""

    def __init__(
        self,
        snapshot_loader: Callable[[], Awaitable[dict[str, Any]]],
        *,
        poll_seconds: float = 5.0,
        heartbeat_seconds: float = 15.0,
        replay_capacity: int = 128,
        max_subscribers: int = 12,
        max_payload_bytes: int = 4096,
        queue_capacity: int = 16,
    ) -> None:
        self._snapshot_loader = snapshot_loader
        self.poll_seconds = poll_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.replay_capacity = replay_capacity
        self.max_subscribers = max_subscribers
        self.max_payload_bytes = max_payload_bytes
        self.queue_capacity = queue_capacity
        self._events: deque[OverviewEvent] = deque(maxlen=replay_capacity)
        self._subscribers: set[asyncio.Queue[OverviewEvent | object]] = set()
        self._lock = asyncio.Lock()
        self._next_event_id = 1
        self._last_fingerprint: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._stopped.clear()
            self._task = asyncio.create_task(
                self._run(), name="mission-control-overview-events"
            )

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        async with self._lock:
            for queue in self._subscribers:
                try:
                    queue.put_nowait(_CLOSE)
                except asyncio.QueueFull:
                    pass
            self._subscribers.clear()

    async def subscribe(self, cursor: str | None) -> OverviewSubscription:
        parsed, cursor_state = self._parse_cursor(cursor)
        queue: asyncio.Queue[OverviewEvent | object] = asyncio.Queue(
            maxsize=self.queue_capacity
        )
        async with self._lock:
            if len(self._subscribers) >= self.max_subscribers:
                raise SubscriberLimitExceeded("overview subscriber budget reached")
            replay = self._replay_after(parsed, cursor_state)
            self._subscribers.add(queue)
        return OverviewSubscription(
            replay=replay, queue=queue, cursor_state=cursor_state
        )

    async def unsubscribe(self, subscription: OverviewSubscription) -> None:
        async with self._lock:
            self._subscribers.discard(subscription.queue)

    async def publish_snapshot(self, snapshot: dict[str, Any]) -> OverviewEvent | None:
        return await self._publish("overview.changed", self._snapshot_payload(snapshot))

    async def publish_unavailable(self) -> OverviewEvent | None:
        return await self._publish(
            "overview.unavailable",
            {
                "schema_version": EVENT_SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "freshness": "unavailable",
                "reason": "control_plane_unreachable",
            },
        )

    async def _run(self) -> None:
        while not self._stopped.is_set():
            async with self._lock:
                has_subscribers = bool(self._subscribers)
            if has_subscribers:
                try:
                    await self.publish_snapshot(await self._snapshot_loader())
                except Exception:  # noqa: BLE001 - The event must not disclose transport internals.
                    await self.publish_unavailable()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                continue

    async def _publish(self, event: str, data: dict[str, Any]) -> OverviewEvent | None:
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("overview event exceeds its payload budget")
        fingerprint = hashlib.sha256(f"{event}:{serialized}".encode()).hexdigest()
        async with self._lock:
            if fingerprint == self._last_fingerprint:
                return None
            self._last_fingerprint = fingerprint
            record = OverviewEvent(self._next_event_id, event, data)
            self._next_event_id += 1
            self._events.append(record)
            for queue in tuple(self._subscribers):
                try:
                    queue.put_nowait(record)
                except asyncio.QueueFull:
                    self._subscribers.discard(queue)
            return record

    def _replay_after(
        self, cursor: int | None, cursor_state: str | None
    ) -> list[OverviewEvent]:
        if cursor_state is not None:
            return []
        if cursor is None:
            return [self._events[-1]] if self._events else []
        if self._events and cursor < self._events[0].event_id - 1:
            return []
        return [event for event in self._events if event.event_id > cursor]

    def _parse_cursor(self, cursor: str | None) -> tuple[int | None, str | None]:
        if cursor is None or cursor == "":
            return None, None
        if not cursor.isdecimal():
            return None, "invalid"
        value = int(cursor)
        if self._events and value < self._events[0].event_id - 1:
            return value, "expired"
        return value, None

    @staticmethod
    def _snapshot_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
        provenance = (
            snapshot.get("provenance")
            if isinstance(snapshot.get("provenance"), dict)
            else {}
        )
        approval = (
            snapshot.get("approval_center")
            if isinstance(snapshot.get("approval_center"), dict)
            else {}
        )
        counts = (
            approval.get("counts") if isinstance(approval.get("counts"), dict) else {}
        )
        operations = (
            snapshot.get("operation_summary")
            if isinstance(snapshot.get("operation_summary"), dict)
            else {}
        )
        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "generated_at": provenance.get("generated_at")
            or datetime.now(timezone.utc).isoformat(),
            "freshness": provenance.get("freshness", "unknown"),
            "active_operations": int(operations.get("active_total") or 0),
            "actionable_approvals": int(counts.get("actionable") or 0),
        }
