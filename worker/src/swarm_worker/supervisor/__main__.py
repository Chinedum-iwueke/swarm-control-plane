from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal

from pydantic import ValidationError

from swarm_worker.supervisor.config import SupervisorSettings
from swarm_worker.supervisor.service import (
    MissionSupervisor,
    SupervisorAuthenticationError,
    SupervisorError,
)


async def _run(command: str, log_level: str) -> int:
    logging.basicConfig(level=log_level, format="%(message)s")
    logger = logging.getLogger("mission_supervisor")
    try:
        settings = SupervisorSettings()
    except ValidationError:
        logger.critical(json.dumps({"event": "supervisor_configuration_failed"}))
        return 2
    supervisor = MissionSupervisor(settings)
    try:
        if command in {"check", "once"}:
            results = await supervisor.reconcile()
            logger.info(
                json.dumps(
                    {
                        "event": f"supervisor_{command}_succeeded",
                        "missions": len(results),
                    }
                )
            )
            return 0
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for requested in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(requested, stop.set)
        delay = settings.swarm_supervisor_poll_interval_seconds
        while not stop.is_set():
            try:
                results = await supervisor.reconcile()
                delay = settings.swarm_supervisor_poll_interval_seconds
                for result in results:
                    if result["action"] not in {"waiting", "waiting_approval"}:
                        logger.info(
                            json.dumps(
                                {
                                    "event": "mission_reconciled",
                                    "mission_id": result["mission"]["id"],
                                    "action": result["action"],
                                }
                            )
                        )
            except SupervisorAuthenticationError:
                logger.critical(
                    json.dumps({"event": "supervisor_authentication_failed"})
                )
                return 3
            except SupervisorError:
                delay = min(120, max(delay * 2, 5))
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
        return 0
    finally:
        await supervisor.close()


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
