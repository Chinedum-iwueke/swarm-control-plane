import asyncio
import io
import json
from collections.abc import Sequence
from uuid import UUID

import pytest

from swarm_worker.__main__ import configure_logging
from swarm_worker.api_client import AuthenticationError, ConnectionError
from swarm_worker.daemon import (
    EXIT_AUTHENTICATION_ERROR,
    EXIT_OK,
    WorkerDaemon,
)
from swarm_worker.service import NoWorkOutcome, ReleasedOutcome


def completed_outcome() -> ReleasedOutcome:
    return ReleasedOutcome(
        task_id=UUID("22222222-2222-4222-8222-222222222222"),
        task_number="TASK-1",
        reason_category="test",
    )


class SequenceService:
    def __init__(
        self,
        values: Sequence[object],
        *,
        fallback: object | None = None,
    ) -> None:
        self.values = list(values)
        self.fallback = fallback or NoWorkOutcome()
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.heartbeats = 0

    async def run_once(self):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.heartbeats += 1
        try:
            value = self.values.pop(0) if self.values else self.fallback
            if isinstance(value, Exception):
                raise value
            await asyncio.sleep(0)
            return value
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_no_work_uses_configured_poll_interval() -> None:
    shutdown = asyncio.Event()
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)
        shutdown.set()

    service = SequenceService([NoWorkOutcome()])
    daemon = WorkerDaemon(
        service,
        poll_interval_seconds=7.5,
        shutdown_event=shutdown,
        sleep=sleep,
    )

    assert await daemon.run() == EXIT_OK
    assert service.calls == 1
    assert delays == [7.5]


@pytest.mark.asyncio
async def test_backoff_increases_and_is_bounded() -> None:
    shutdown = asyncio.Event()
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) == 4:
            shutdown.set()

    service = SequenceService(
        [
            ConnectionError("offline"),
            ConnectionError("offline"),
            ConnectionError("offline"),
            ConnectionError("offline"),
        ]
    )
    daemon = WorkerDaemon(
        service,
        poll_interval_seconds=10,
        shutdown_event=shutdown,
        backoff_initial_seconds=1,
        backoff_max_seconds=4,
        jitter=lambda: 1.0,
        sleep=sleep,
    )

    assert await daemon.run() == EXIT_OK
    assert delays == [1, 2, 4, 4]


@pytest.mark.asyncio
async def test_backoff_resets_after_success() -> None:
    shutdown = asyncio.Event()
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) == 2:
            shutdown.set()

    service = SequenceService(
        [
            ConnectionError("offline"),
            completed_outcome(),
            ConnectionError("offline"),
        ]
    )
    daemon = WorkerDaemon(
        service,
        poll_interval_seconds=10,
        shutdown_event=shutdown,
        backoff_initial_seconds=2,
        backoff_max_seconds=20,
        jitter=lambda: 1.0,
        sleep=sleep,
    )

    assert await daemon.run() == EXIT_OK
    assert delays == [2, 2]
    assert service.calls == 3


@pytest.mark.asyncio
async def test_authentication_error_exits_without_retry() -> None:
    service = SequenceService([AuthenticationError("rejected")])
    daemon = WorkerDaemon(service, poll_interval_seconds=1)

    assert await daemon.run() == EXIT_AUTHENTICATION_ERROR
    assert service.calls == 1


@pytest.mark.asyncio
async def test_cycles_never_overlap_and_idle_heartbeat_continues() -> None:
    shutdown = asyncio.Event()
    sleeps = 0

    async def sleep(delay: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            shutdown.set()

    service = SequenceService([NoWorkOutcome(), NoWorkOutcome(), NoWorkOutcome()])
    daemon = WorkerDaemon(
        service,
        poll_interval_seconds=0.1,
        shutdown_event=shutdown,
        sleep=sleep,
    )

    assert await daemon.run() == EXIT_OK
    assert service.calls == 3
    assert service.max_active == 1
    assert service.heartbeats == 3


class BlockingService:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.cancelled = False
        self.release_attempted = False

    async def run_once(self):
        self.calls += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            self.release_attempted = True
            raise


@pytest.mark.asyncio
async def test_shutdown_cancels_active_cycle_and_prevents_new_lease() -> None:
    shutdown = asyncio.Event()
    service = BlockingService()
    daemon = WorkerDaemon(
        service,
        poll_interval_seconds=1,
        shutdown_event=shutdown,
        shutdown_timeout_seconds=1,
    )
    running = asyncio.create_task(daemon.run())
    await service.started.wait()

    daemon.request_shutdown()

    assert await running == EXIT_OK
    assert service.calls == 1
    assert service.cancelled is True
    assert service.release_attempted is True


def test_structured_logging_redacts_credentials() -> None:
    stream = io.StringIO()
    agent_token = "swarm_ag_abcdef_super-secret"
    lease_token = "swarm_lt_abcdef_other-secret"
    logger = configure_logging(
        "INFO",
        secrets=(agent_token,),
        stream=stream,
    )

    logger.critical(
        "failed Authorization: Bearer %s lease=%s",
        agent_token,
        lease_token,
    )

    output = stream.getvalue()
    document = json.loads(output)
    assert document["event"].count("[REDACTED]") >= 2
    assert agent_token not in output
    assert lease_token not in output
    assert "Authorization: [REDACTED]" in output
