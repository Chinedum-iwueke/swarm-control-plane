"""Explicit billing isolation for OpenAI-backed worker processes."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import httpx


def provider_key(environment: Mapping[str, str] | None = None) -> str:
    env = os.environ if environment is None else environment
    lane = env.get("SWARM_OPENAI_BILLING_LANE", "subscription")
    if lane not in {"subscription", "api"}:
        raise ValueError("SWARM_OPENAI_BILLING_LANE must be subscription or api")
    return "codex" if lane == "subscription" else "openai-api"


def route_command(args: Sequence[str], environment: dict[str, str]) -> tuple[str, ...]:
    """Route only Codex; never expose the API key to deterministic child tools."""
    command = tuple(args)
    if Path(command[0]).name != "codex" or provider_key() == "codex":
        return command
    key_path = os.environ.get("SWARM_OPENAI_API_KEY_FILE")
    home = os.environ.get("SWARM_OPENAI_API_CODEX_HOME")
    if not key_path or not home or home == environment.get("CODEX_HOME"):
        raise ValueError("API lane requires a key file and a separate Codex home")
    key = Path(key_path).read_text().strip()
    if not key:
        raise ValueError("OpenAI API key file is empty")
    environment["INVARIANCE_OPENAI_API_KEY"] = key
    environment["CODEX_HOME"] = home
    # A named API provider prevents accidental use of the subscription auth cache.
    options = (
        "-c",
        'model_provider="invariance_api"',
        "-c",
        'model_providers.invariance_api.name="OpenAI API"',
        "-c",
        'model_providers.invariance_api.base_url="https://api.openai.com/v1"',
        "-c",
        'model_providers.invariance_api.env_key="INVARIANCE_OPENAI_API_KEY"',
        "-c",
        'model_providers.invariance_api.wire_api="responses"',
        "-c",
        "model_providers.invariance_api.requires_openai_auth=false",
    )
    return (*command, *options)


def worker_providers(task_types: list[str]) -> list[str]:
    if set(task_types) & {
        "engineering_mission",
        "alpha_discovery",
        "alpha_strategy_review",
        "alpha_method_design",
        "founder_request",
    }:
        return [provider_key()]
    return []


async def model_call_allowed() -> bool:
    return (await model_capacity_permit()).get('allowed') is True


async def model_capacity_permit() -> dict:
    url, token = os.environ.get("SWARM_API_URL"), os.environ.get("SWARM_AGENT_TOKEN")
    if not token:
        return {'allowed': True, 'recovery_token': 'offline:initial'}
    if not url or not token:
        return {'allowed': False}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                url.rstrip("/").removesuffix("/v1")
                + f"/v1/agent/provider-capacity/{provider_key()}/permit",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                return {'allowed': False}
            return {'allowed': result.get('allowed') is True,
                    'recovery_token': result.get('recovery_token')}
    except (httpx.HTTPError, ValueError):
        return {'allowed': False}
