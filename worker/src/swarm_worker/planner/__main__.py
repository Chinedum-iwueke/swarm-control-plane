from __future__ import annotations

import argparse
import asyncio
import json
import random
import signal

from pydantic import ValidationError

from swarm_worker.api_client import (
    AuthenticationError,
    ConnectionError,
    ServerError,
    SwarmAPIClient,
)
from swarm_worker.config import WorkerSettings
from swarm_worker.planner.config import PlannerSettings
from swarm_worker.planner.engine import CodexProposalPlanner, PlannerError
from swarm_worker.planner.service import FounderIntakePlannerService


async def _run_once(settings: PlannerSettings) -> int:
    settings.prepare()
    worker_settings = WorkerSettings(
        swarm_api_url=settings.swarm_api_url,
        swarm_agent_token=settings.swarm_agent_token,
        swarm_agent_slug=settings.swarm_agent_slug,
        swarm_machine=settings.swarm_machine,
        swarm_lease_seconds=settings.swarm_lease_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
    )
    planner = CodexProposalPlanner(
        codex_binary=settings.swarm_codex_binary,
        codex_home=settings.swarm_codex_home,
        model=settings.swarm_codex_model,
        timeout_seconds=settings.swarm_planner_timeout_seconds,
        working_directory=settings.swarm_planner_workspace,
    )
    async with SwarmAPIClient(worker_settings) as api:
        outcome = await FounderIntakePlannerService(
            settings, api=api, planner=planner
        ).run_once()
    print(json.dumps({"event": "planner_once_complete", "outcome": outcome.kind}))
    return 0 if outcome.kind in {"no_work", "succeeded", "released"} else 1


async def _run_forever(settings: PlannerSettings) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)
    backoff = 1.0
    while not stop.is_set():
        try:
            result = await _run_once(settings)
            backoff = 1.0
            delay = (
                settings.swarm_poll_interval_seconds
                if result == 0
                else min(30.0, backoff)
            )
        except (ConnectionError, ServerError):
            delay = min(60.0, backoff) + random.uniform(0, backoff / 4)
            backoff = min(60.0, backoff * 2)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            continue
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restricted founder intake planner")
    parser.add_argument("command", choices=("check", "once", "run"))
    args = parser.parse_args()
    try:
        settings = PlannerSettings()
        if args.command == "check":
            settings.prepare()
            if not settings.swarm_codex_binary.is_file():
                raise PlannerError("Codex executable is unavailable.")
            print(json.dumps({"event": "planner_check_succeeded"}))
            return 0
        if args.command == "once":
            return asyncio.run(_run_once(settings))
        return asyncio.run(_run_forever(settings))
    except (ValidationError, PlannerError, AuthenticationError) as exc:
        print(
            json.dumps(
                {"event": "planner_error", "error": type(exc).__name__}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
