from __future__ import annotations

import asyncio
import os
import re
import signal
import tempfile
from pathlib import Path

from swarm_worker.model_lane import provider_key, route_command
from swarm_worker.models import StepExecutionResult


async def probe_capacity(codex_home: Path, model: str) -> tuple[bool, str | None]:
    """A bounded no-task availability check, never a whole engineering retry."""
    with tempfile.TemporaryDirectory(prefix="swarm-provider-probe-") as directory:
        output = Path(directory) / "response.txt"
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": directory,
            "CODEX_HOME": str(codex_home),
            "NODE_OPTIONS": "--jitless",
        }
        args = route_command(
            [
                "codex",
                "exec",
                "--ignore-user-config",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "-m",
                model,
                "-o",
                str(output),
                "Reply with exactly READY. Do not use tools or inspect files.",
            ],
            env,
        )
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=directory,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=90)
        except TimeoutError:
            os.killpg(process.pid, signal.SIGKILL)
            await process.communicate()
            return (
                False,
                "Provider availability probe timed out; capacity remains unconfirmed.",
            )
        healthy = (
            process.returncode == 0
            and output.is_file()
            and output.read_text().strip() == "READY"
        )
        return healthy, None if healthy else " ".join(
            stderr.decode(errors="replace").split()
        )[-2000:] or "Provider probe did not return READY."


CAPACITY_MARKERS = (
    "credit limit",
    "credits exhausted",
    "quota exceeded",
    "quota exhausted",
    "no premium requests remaining",
    "premium request limit",
    "rate limit",
    "too many requests",
    "at capacity",
    "usage limit",
)


def detect_provider_capacity(
    steps: list[StepExecutionResult],
    attempt_directory: Path,
    provider_by_step: dict[str, str],
) -> dict[str, object] | None:
    """Return bounded provider-capacity evidence from a failed model step."""

    for step in reversed(steps):
        provider = provider_by_step.get(step.name)
        if provider is None or step.success:
            continue
        try:
            message = (attempt_directory / step.stderr_log).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        lowered = message.lower()
        if not any(marker in lowered for marker in CAPACITY_MARKERS):
            continue
        retry_after_seconds = 21_600
        delay = re.search(
            r"(?:try again|retry)(?: in)?\s+(\d+)\s*(seconds?|minutes?|hours?)",
            lowered,
        )
        if delay and "usage limit" not in lowered and "quota" not in lowered:
            value = int(delay.group(1))
            unit = delay.group(2)
            multiplier = (
                3600
                if unit.startswith("hour")
                else 60
                if unit.startswith("minute")
                else 1
            )
            retry_after_seconds = max(60, min(21_600, value * multiplier))
        compact = " ".join(message.split())
        return {
            "provider": provider_key() if provider == "codex" else provider,
            "failure_summary": compact[-2000:] or "Provider capacity exhausted.",
            "retry_after_seconds": retry_after_seconds,
        }
    return None
