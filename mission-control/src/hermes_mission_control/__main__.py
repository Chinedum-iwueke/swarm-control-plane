from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import uvicorn

from .app import create_app
from .config import MissionControlSettings
from .control_plane import ControlPlaneClient
from .knowledge import KnowledgeStore
from .research_inbox import research_inbox_status, sync_research_inbox


def main() -> int:
    parser = argparse.ArgumentParser(prog="hermes-mission-control")
    parser.add_argument("command", choices=("run", "check", "sync", "sync-status"))
    parser.add_argument("--inbox")
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()
    try:
        settings = MissionControlSettings()
        if args.inbox:
            settings = settings.model_copy(
                update={"research_inbox_directory": Path(args.inbox)}
            )
        settings.prepare()
        store = KnowledgeStore(settings.database_path, settings.allowed_knowledge_roots)
        store.initialize()
        if args.command == "check":
            return asyncio.run(_check(settings, store))
        if args.command == "sync":
            return asyncio.run(_sync(settings, finalize_only=args.finalize_only))
        if args.finalize_only:
            raise ValueError("--finalize-only is valid only with the sync command.")
        if args.command == "sync-status":
            print(json.dumps(research_inbox_status(settings), indent=2, sort_keys=True))
            return 0
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            log_level=args.log_level,
            access_log=False,
        )
        return 0
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"event": "mission_control_error", "detail": str(exc)}))
        return 2


async def _check(settings: MissionControlSettings, store: KnowledgeStore) -> int:
    client = ControlPlaneClient(settings)
    try:
        dashboard = await client.dashboard()
    finally:
        await client.close()
    print(
        json.dumps(
            {
                "event": "mission_control_check_succeeded",
                "control_plane": dashboard["health"]["status"],
                "knowledge": store.stats(),
                "roots": [str(path) for path in settings.allowed_knowledge_roots],
            },
            sort_keys=True,
        )
    )
    return 0


async def _sync(
    settings: MissionControlSettings, *, finalize_only: bool = False
) -> int:
    client = ControlPlaneClient(settings)
    try:
        report = await sync_research_inbox(
            settings, client, finalize_only=finalize_only
        )
    finally:
        await client.close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(bool(report["counts"]["failed"] or report["counts"]["rejected"]))


if __name__ == "__main__":
    raise SystemExit(main())
