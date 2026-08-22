from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProbeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWARM_FLEET_", extra="ignore")

    api_url: str
    agent_token_file: Path
    machine: str = Field(pattern=r"^[a-z0-9-]+$")
    interval_seconds: float = Field(default=20, ge=15, le=60)
    services: str = ""
    disk_path: Path = Path("/")
    state_path: Path = Path("/var/lib/invariance-swarm-fleet-probe/state.json")

    @property
    def service_names(self) -> list[str]:
        values = [item.strip() for item in self.services.split(",") if item.strip()]
        if len(values) > 30 or len(values) != len(set(values)):
            raise ValueError("SWARM_FLEET_SERVICES must contain up to 30 unique names.")
        return values


@dataclass(frozen=True)
class CpuCounters:
    total: int
    idle: int


def collect(settings: ProbeSettings) -> dict:
    previous = _read_state(settings.state_path)
    cpu = _cpu()
    vm = _key_values(Path("/proc/vmstat"))
    current = {
        "cpu_total": cpu.total,
        "cpu_idle": cpu.idle,
        "pswpin": vm.get("pswpin", 0),
        "pswpout": vm.get("pswpout", 0),
        "oom_kill": vm.get("oom_kill", 0),
    }
    _write_state(settings.state_path, current)
    memory = _key_values(Path("/proc/meminfo"))
    total_memory = max(memory.get("MemTotal", 0), 1)
    total_swap = memory.get("SwapTotal", 0)
    available = memory.get("MemAvailable", 0)
    free_swap = memory.get("SwapFree", 0)
    disk = os.statvfs(settings.disk_path)
    cpu_delta = max(cpu.total - int(previous.get("cpu_total", cpu.total)), 1)
    idle_delta = max(cpu.idle - int(previous.get("cpu_idle", cpu.idle)), 0)
    load = os.getloadavg()[0] / max(os.cpu_count() or 1, 1)
    return {
        "schema_version": "fleet-observation-v1.0.0",
        "sample_id": f"{int(time.time())}-{uuid.uuid4().hex[:12]}",
        "machine": settings.machine,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "cpu_utilization_percent": _percent(cpu_delta - idle_delta, cpu_delta),
            "load_per_core": round(load, 4),
            "memory_available_percent": _percent(available, total_memory),
            "swap_used_percent": _percent(total_swap - free_swap, total_swap)
            if total_swap
            else 0.0,
            "swap_in_bytes_delta": max(
                vm.get("pswpin", 0) - int(previous.get("pswpin", vm.get("pswpin", 0))),
                0,
            )
            * os.sysconf("SC_PAGE_SIZE"),
            "swap_out_bytes_delta": max(
                vm.get("pswpout", 0)
                - int(previous.get("pswpout", vm.get("pswpout", 0))),
                0,
            )
            * os.sysconf("SC_PAGE_SIZE"),
            "disk_used_percent": _percent(disk.f_blocks - disk.f_bavail, disk.f_blocks),
            "inode_used_percent": _percent(disk.f_files - disk.f_favail, disk.f_files),
            "cpu_pressure_avg10": _pressure("cpu"),
            "io_pressure_avg10": _pressure("io"),
            "memory_pressure_avg10": _pressure("memory"),
            "uptime_seconds": float(Path("/proc/uptime").read_text().split()[0]),
            "oom_kills_delta": max(
                vm.get("oom_kill", 0)
                - int(previous.get("oom_kill", vm.get("oom_kill", 0))),
                0,
            ),
        },
        "services": [_service(name) for name in settings.service_names],
    }


def publish(settings: ProbeSettings, payload: dict) -> None:
    token = settings.agent_token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("Fleet probe credential is empty.")
    request = urllib.request.Request(
        f"{settings.api_url.rstrip('/')}/v1/agent/fleet/observations",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 201}:
                raise RuntimeError(f"Control plane returned HTTP {response.status}.")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Control plane returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Control plane is unreachable.") from exc


def _cpu() -> CpuCounters:
    values = [
        int(value)
        for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    ]
    return CpuCounters(
        total=sum(values), idle=values[3] + (values[4] if len(values) > 4 else 0)
    )


def _key_values(path: Path) -> dict[str, int]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.replace(":", "").split()
        if len(fields) >= 2 and fields[1].isdigit():
            result[fields[0]] = int(fields[1])
    return result


def _pressure(resource: str) -> float:
    path = Path("/proc/pressure") / resource
    if not path.exists():
        return 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("some "):
            values = dict(item.split("=", 1) for item in line.split()[1:])
            return float(values["avg10"])
    return 0.0


def _service(name: str) -> dict[str, str]:
    completed = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
    )
    status = completed.stdout.strip()
    if status not in {"active", "inactive", "failed"}:
        status = "unknown"
    return {"name": name, "status": status}


def _percent(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes bounded Linux fleet probe")
    parser.add_argument("command", choices=("check", "once", "run"))
    args = parser.parse_args()
    settings = ProbeSettings()
    if os.geteuid() == 0:
        raise RuntimeError("Fleet probe must not run as root.")
    if not shutil.which("systemctl"):
        raise RuntimeError("systemctl is unavailable.")
    if args.command == "check":
        collect(settings)
        print(
            json.dumps(
                {"event": "fleet_probe_check_succeeded", "machine": settings.machine}
            )
        )
        return 0
    while True:
        publish(settings, collect(settings))
        print(
            json.dumps(
                {"event": "fleet_observation_published", "machine": settings.machine}
            ),
            flush=True,
        )
        if args.command == "once":
            return 0
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
