from __future__ import annotations

import argparse
import asyncio
import json
import signal

from pydantic import ValidationError

from .config import GatewaySettings
from .control_plane import FounderChannelClient
from .gateway import RestrictedTelegramGateway
from .store import HandoffStore
from .telegram import TelegramClient


async def run(command: str) -> int:
    settings = GatewaySettings()
    settings.prepare()
    store = HandoffStore(settings.data_root / "gateway.sqlite3")
    store.initialize()
    telegram = TelegramClient(settings.bot_token)
    channel = FounderChannelClient(
        settings.api_url, settings.founder_channel_token
    )
    gateway = RestrictedTelegramGateway(
        settings, telegram=telegram, channel=channel, store=store
    )
    try:
        if command == "check":
            await gateway.check()
            print(json.dumps({"event": "telegram_gateway_check_succeeded"}))
            return 0
        if command == "once":
            await gateway.check()
            await gateway.run_once()
            return 0
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stop.set)
        await gateway.run(stop)
        return 0
    finally:
        await telegram.close()
        await channel.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "once", "run"))
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.command))
    except (ValidationError, ValueError, RuntimeError) as exc:
        print(
            json.dumps(
                {"event": "telegram_gateway_error", "error": type(exc).__name__}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
