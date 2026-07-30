from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from .app import create_app
from .config import MissionControlSettings
from .control_plane import ControlPlaneClient
from .knowledge import KnowledgeStore


def main() -> int:
    parser = argparse.ArgumentParser(prog="hermes-mission-control")
    parser.add_argument("command", choices=("run", "check"))
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()
    try:
        settings = MissionControlSettings()
        settings.prepare()
        store = KnowledgeStore(
            settings.database_path, settings.allowed_knowledge_roots
        )
        store.initialize()
        if args.command == "check":
            return asyncio.run(_check(settings, store))
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


async def _check(
    settings: MissionControlSettings, store: KnowledgeStore
) -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())

