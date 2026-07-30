from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any

from swarm_worker.api_client import (
    AuthenticationError,
    ConnectionError,
    ServerError,
)
from swarm_worker.service import (
    NoWorkOutcome,
    PausedOutcome,
    WorkerConfigurationError,
    WorkerService,
)

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_AUTHENTICATION_ERROR = 3


class WorkerDaemon:
    def __init__(
        self,
        service: WorkerService,
        *,
        poll_interval_seconds: float,
        shutdown_event: asyncio.Event | None = None,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
        shutdown_timeout_seconds: float = 40.0,
        jitter: Callable[[], float] | None = None,
        sleep: Callable[[float], Coroutine[Any, Any, None]] = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        if (
            poll_interval_seconds <= 0
            or backoff_initial_seconds <= 0
            or backoff_max_seconds < backoff_initial_seconds
            or shutdown_timeout_seconds <= 0
        ):
            raise ValueError("Daemon timing values are invalid.")
        self._service = service
        self._poll_interval_seconds = poll_interval_seconds
        self._shutdown = shutdown_event or asyncio.Event()
        self._backoff_initial_seconds = backoff_initial_seconds
        self._backoff_max_seconds = backoff_max_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._jitter = jitter or (lambda: random.uniform(0.8, 1.2))
        self._sleep = sleep
        self._logger = logger or logging.getLogger("swarm_worker.daemon")
        self._active_cycle: asyncio.Task[Any] | None = None

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown

    def request_shutdown(self) -> None:
        if not self._shutdown.is_set():
            self._logger.info("shutdown_requested")
            self._shutdown.set()

    async def run(self) -> int:
        consecutive_failures = 0
        self._logger.info("daemon_started")

        while not self._shutdown.is_set():
            self._active_cycle = asyncio.create_task(
                self._service.run_once(),
                name="worker-run-once",
            )
            shutdown_wait = asyncio.create_task(
                self._shutdown.wait(),
                name="worker-shutdown-wait",
            )
            done, _ = await asyncio.wait(
                {self._active_cycle, shutdown_wait},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if shutdown_wait in done and self._shutdown.is_set():
                await self._stop_active_cycle()
                self._active_cycle = None
                self._logger.info("daemon_stopped", extra={"exit_code": EXIT_OK})
                return EXIT_OK

            shutdown_wait.cancel()
            await self._consume_cancelled(shutdown_wait)
            cycle = self._active_cycle
            self._active_cycle = None

            try:
                outcome = cycle.result()
            except AuthenticationError:
                self._logger.critical(
                    "authentication_failed",
                    extra={"exit_code": EXIT_AUTHENTICATION_ERROR},
                )
                return EXIT_AUTHENTICATION_ERROR
            except WorkerConfigurationError:
                self._logger.critical(
                    "configuration_failed",
                    extra={"exit_code": EXIT_CONFIGURATION_ERROR},
                )
                return EXIT_CONFIGURATION_ERROR
            except (ConnectionError, ServerError) as exc:
                consecutive_failures += 1
                delay = self._backoff_delay(consecutive_failures)
                self._logger.warning(
                    "temporary_control_plane_failure",
                    extra={
                        "error_category": type(exc).__name__,
                        "retry_delay_seconds": delay,
                    },
                )
                if await self._wait_or_shutdown(delay):
                    break
                continue
            except Exception as exc:  # noqa: BLE001 - top-level cycle boundary
                self._logger.error(
                    "worker_cycle_failed",
                    extra={
                        "error_category": type(exc).__name__,
                        "exit_code": EXIT_RUNTIME_ERROR,
                    },
                )
                return EXIT_RUNTIME_ERROR

            consecutive_failures = 0
            self._logger.info(
                "worker_cycle_complete",
                extra={"outcome": outcome.status},
            )
            if isinstance(
                outcome,
                (NoWorkOutcome, PausedOutcome),
            ) and await self._wait_or_shutdown(self._poll_interval_seconds):
                break

        self._logger.info("daemon_stopped", extra={"exit_code": EXIT_OK})
        return EXIT_OK

    def _backoff_delay(self, failure_count: int) -> float:
        exponential = self._backoff_initial_seconds * (2 ** (failure_count - 1))
        bounded = min(exponential, self._backoff_max_seconds)
        jittered = bounded * self._jitter()
        return max(0.0, min(jittered, self._backoff_max_seconds))

    async def _wait_or_shutdown(self, delay: float) -> bool:
        sleep_task = asyncio.create_task(self._sleep(delay))
        shutdown_wait = asyncio.create_task(self._shutdown.wait())
        done, _ = await asyncio.wait(
            {sleep_task, shutdown_wait},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if shutdown_wait in done and self._shutdown.is_set():
            sleep_task.cancel()
            await self._consume_cancelled(sleep_task)
            return True
        shutdown_wait.cancel()
        await self._consume_cancelled(shutdown_wait)
        await sleep_task
        return self._shutdown.is_set()

    async def _stop_active_cycle(self) -> None:
        cycle = self._active_cycle
        if cycle is None or cycle.done():
            return
        self._logger.info("active_cycle_cancelling")
        cycle.cancel()
        try:
            await asyncio.wait_for(
                cycle,
                timeout=self._shutdown_timeout_seconds,
            )
        except asyncio.CancelledError:
            self._logger.info("active_cycle_cancelled")
        except asyncio.TimeoutError:
            self._logger.error("active_cycle_shutdown_timeout")
        except Exception as exc:  # noqa: BLE001 - shutdown boundary
            self._logger.error(
                "active_cycle_shutdown_failed",
                extra={"error_category": type(exc).__name__},
            )

    @staticmethod
    async def _consume_cancelled(task: asyncio.Task[Any]) -> None:
        try:
            await task
        except asyncio.CancelledError:
            pass
