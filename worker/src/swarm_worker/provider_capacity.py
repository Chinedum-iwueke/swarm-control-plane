from __future__ import annotations

import re
from pathlib import Path

from swarm_worker.models import StepExecutionResult

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
        retry_after_seconds = 900
        delay = re.search(
            r"(?:try again|retry)(?: in)?\s+(\d+)\s*(seconds?|minutes?|hours?)",
            lowered,
        )
        if delay:
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
            "provider": provider,
            "failure_summary": compact[-2000:] or "Provider capacity exhausted.",
            "retry_after_seconds": retry_after_seconds,
        }
    return None
