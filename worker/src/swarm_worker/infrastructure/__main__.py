from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal

from pydantic import ValidationError

from swarm_worker.api_client import AuthenticationError, ConnectionError, ServerError
from swarm_worker.infrastructure.config import InfrastructureSettings
from swarm_worker.infrastructure.runbooks import load_runbook
from swarm_worker.infrastructure.service import InfrastructureService
from swarm_worker.role_package import load_role_package


def _logger(level: str) -> logging.Logger:
    logger = logging.getLogger("swarm_infrastructure_worker")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


async def _run(command: str, level: str) -> int:
    logger = _logger(level)
    try:
        settings = InfrastructureSettings()
    except ValidationError:
        logger.critical(json.dumps({"event": "configuration_failed"}))
        return 2
    service = InfrastructureService(settings)
    if command == "check":
        try:
            settings.prepare_directories()
            package = load_role_package(
                settings.swarm_infrastructure_role_manifest,
                settings.swarm_infrastructure_runbook_directory,
            )
            for artifact in package.manifest.workflows:
                load_runbook(
                    settings.swarm_infrastructure_runbook_directory / artifact.file
                )
            if not settings.swarm_broker_socket.exists():
                raise RuntimeError("Broker socket is unavailable.")
            api = service._api_factory(settings)
            try:
                identity = await api.get_identity()
            finally:
                await api.aclose()
            if (
                identity.slug != settings.swarm_agent_slug
                or identity.machine != settings.swarm_machine
                or not identity.is_enabled
            ):
                raise RuntimeError("Agent identity mismatch.")
            logger.info(json.dumps({"event": "infrastructure_check_succeeded"}))
            return 0
        except AuthenticationError:
            logger.critical(json.dumps({"event": "authentication_failed"}))
            return 3
        except Exception as exc:  # noqa: BLE001 - CLI diagnostic boundary
            logger.error(
                json.dumps(
                    {
                        "event": "infrastructure_check_failed",
                        "error": type(exc).__name__,
                    }
                )
            )
            return 1
    if command == "once":
        try:
            outcome = await service.run_once()
        except AuthenticationError:
            logger.critical(json.dumps({"event": "authentication_failed"}))
            return 3
        logger.info(
            json.dumps(
                {"event": "infrastructure_once_complete", "outcome": outcome.status}
            )
        )
        return 0
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for requested in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(requested, stop.set)
    delay = settings.swarm_poll_interval_seconds
    while not stop.is_set():
        try:
            outcome = await service.run_once()
            delay = settings.swarm_poll_interval_seconds
            if outcome.status != "no_work":
                logger.info(
                    json.dumps(
                        {"event": "infrastructure_cycle", "outcome": outcome.status}
                    )
                )
        except AuthenticationError:
            logger.critical(json.dumps({"event": "authentication_failed"}))
            return 3
        except (ConnectionError, ServerError):
            delay = min(120, max(delay * 2, 5))
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except (TimeoutError, asyncio.TimeoutError):
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "once", "check"))
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.command, args.log_level))


if __name__ == "__main__":
    raise SystemExit(main())
