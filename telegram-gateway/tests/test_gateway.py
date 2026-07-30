from __future__ import annotations

from pathlib import Path

import pytest

from hermes_telegram_gateway.config import GatewaySettings
from hermes_telegram_gateway.gateway import (
    RestrictedTelegramGateway,
    classify_request,
)
from hermes_telegram_gateway.store import HandoffStore


def settings(tmp_path: Path) -> GatewaySettings:
    bot = tmp_path / "bot"
    channel = tmp_path / "channel"
    bot.write_text("bot-token-that-is-long-enough")
    channel.write_text("channel-token-that-is-long-enough")
    bot.chmod(0o600)
    channel.chmod(0o600)
    return GatewaySettings(
        bot_token_file=bot,
        founder_channel_token_file=channel,
        founder_user_id=123,
        founder_chat_id=456,
        api_url="http://control-plane.test",
        data_root=tmp_path / "data",
    )


class Telegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, dict]] = []

    async def get_me(self):
        return {"username": "hermes_test_bot"}

    async def updates(self, *_):
        return []

    async def send(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))


class Channel:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.proposal_decisions: list[tuple[str, str, str]] = []

    async def create_request(self, payload):
        self.created.append(payload)
        return {"task_number": "FOUNDER-1"}

    async def proposals(self):
        return []

    async def tasks(self):
        return []

    async def approvals(self):
        return []

    async def decide_proposal(self, proposal_id, action, reason):
        self.proposal_decisions.append((proposal_id, action, reason))
        return {}


@pytest.mark.asyncio
async def test_plain_english_is_structured_and_sender_is_allowlisted(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )

    await gateway._handle_update(
        {
            "message": {
                "from": {"id": 999},
                "chat": {"id": 456},
                "text": "Restart PostgreSQL",
            }
        }
    )
    assert channel.created == []

    await gateway._handle_update(
        {
            "message": {
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Please verify the PostgreSQL backup without changing it.",
            }
        }
    )
    assert channel.created[0]["project"] == "swarm-control-plane"
    assert "command" not in channel.created[0]
    assert channel.created[0]["objective"].startswith("Please verify")


def test_handoff_is_expiring_digest_bound_and_single_use(tmp_path: Path) -> None:
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    token = store.create("proposal", "proposal-id", "a" * 64, 300)
    assert store.resolve(token) == ("proposal", "proposal-id", "a" * 64)
    assert store.consume(token) is True
    assert store.resolve(token) is None
    assert store.consume(token) is False


def test_domain_classification_is_bounded() -> None:
    assert classify_request("Run a research hypothesis") == ("bulletproof_bt", 1)
    assert classify_request("Restart the API") == ("swarm-control-plane", 3)
    assert classify_request("Index my knowledge notes") == ("knowledge", 0)
