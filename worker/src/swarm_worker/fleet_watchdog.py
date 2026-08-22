from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatchdogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWARM_WATCHDOG_", extra="ignore")

    targets: str
    telegram_token_file: Path
    founder_chat_id: int
    interval_seconds: float = Field(default=30, ge=15, le=120)
    failure_samples: int = Field(default=3, ge=2, le=10)
    recovery_samples: int = Field(default=3, ge=2, le=10)
    state_path: Path = Path("/var/lib/invariance-swarm-fleet-watchdog/state.json")

    @property
    def parsed_targets(self) -> dict[str, tuple[str, int]]:
        result: dict[str, tuple[str, int]] = {}
        for value in self.targets.split(","):
            name, separator, address = value.strip().partition("=")
            host, colon, port = address.rpartition(":")
            if not separator or not colon or not name or not host:
                raise ValueError("Watchdog targets must use name=host:port.")
            result[name] = (host, int(port))
        if not 2 <= len(result) <= 10:
            raise ValueError("Watchdog requires between two and ten unique targets.")
        return result


def check_target(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


def cycle(settings: WatchdogSettings) -> list[dict]:
    state = _read_state(settings.state_path)
    notifications = []
    for name, (host, port) in settings.parsed_targets.items():
        reachable = check_target(host, port)
        target = state.setdefault(name, {"failures": 0, "healthy": 0, "alerted": False})
        if reachable:
            target["healthy"] += 1
            target["failures"] = 0
            if target["alerted"] and target["healthy"] >= settings.recovery_samples:
                notifications.append(
                    {
                        "machine": name,
                        "state": "recovered",
                        "detail": "TCP reachability restored.",
                    }
                )
                target["alerted"] = False
        else:
            target["failures"] += 1
            target["healthy"] = 0
            if not target["alerted"] and target["failures"] >= settings.failure_samples:
                notifications.append(
                    {
                        "machine": name,
                        "state": "critical",
                        "detail": "Sustained TCP reachability failure.",
                    }
                )
                target["alerted"] = True
    _write_state(settings.state_path, state)
    return notifications


def notify(settings: WatchdogSettings, event: dict) -> None:
    token = settings.telegram_token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("Watchdog Telegram credential is empty.")
    body = urllib.parse.urlencode(
        {
            "chat_id": str(settings.founder_chat_id),
            "text": (
                f"Independent fleet {event['state']}\n"
                f"{event['machine']}\n{event['detail']}"
            ),
        }
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError("Telegram rejected watchdog notification.")
    except OSError as exc:
        raise RuntimeError("Telegram is unavailable to fleet watchdog.") from exc


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent Hermes fleet watchdog")
    parser.add_argument("command", choices=("check", "once", "run"))
    args = parser.parse_args()
    settings = WatchdogSettings()
    if os.geteuid() == 0:
        raise RuntimeError("Fleet watchdog must not run as root.")
    if args.command == "check":
        _ = settings.parsed_targets
        print(json.dumps({"event": "fleet_watchdog_check_succeeded"}))
        return 0
    while True:
        for event in cycle(settings):
            notify(settings, event)
        if args.command == "once":
            return 0
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
