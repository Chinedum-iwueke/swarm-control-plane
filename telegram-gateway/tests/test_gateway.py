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
        self.approval_values: list[dict] = []
        self.mission_values: list[dict] = []
        self.mission_approvals: list[tuple[str, str]] = []

    async def create_request(self, payload):
        self.created.append(payload)
        return {"task_number": "FOUNDER-1"}

    async def proposals(self):
        return []

    async def tasks(self):
        return []

    async def approvals(self):
        return self.approval_values

    async def missions(self):
        return self.mission_values

    async def approve_mission(self, mission_id, reason):
        self.mission_approvals.append((mission_id, reason))
        return {}

    async def decide_proposal(self, proposal_id, action, reason):
        self.proposal_decisions.append((proposal_id, action, reason))
        return {}


def approval(*, actionable: bool, suffix: str = "02") -> dict:
    return {
        "id": f"approval-{suffix}",
        "task_id": f"task-{suffix}",
        "status": "pending",
        "plan_digest": suffix[-1] * 64,
        "risk_level": 2,
        "scope": {
            "project": "invariance_research",
            "task_type": "infrastructure_operation",
        },
        "task_number": f"INF-RETRY-{suffix}",
        "task_title": "VM2-POSTGRES-ROLLOUT-RETRY-1: stage",
        "operation": "stage-invariance-postgres",
        "actionable": actionable,
    }


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


@pytest.mark.asyncio
async def test_only_actionable_approval_is_notified_with_task_identity(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.approval_values = [
        approval(actionable=False, suffix="03"),
        approval(actionable=False, suffix="04"),
        approval(actionable=False, suffix="05"),
        approval(actionable=True, suffix="02"),
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    await gateway._notify_approvals()

    assert len(telegram.sent) == 1
    message = telegram.sent[0][1]
    assert "INF-RETRY-02" in message
    assert "stage-invariance-postgres" in message
    assert "2" * 64 in message


@pytest.mark.asyncio
async def test_blocked_approval_notifies_when_it_becomes_actionable(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    candidate = approval(actionable=False, suffix="03")
    channel.approval_values = [candidate]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    await gateway._notify_approvals()
    assert telegram.sent == []

    candidate["actionable"] = True
    await gateway._notify_approvals()
    assert len(telegram.sent) == 1


@pytest.mark.asyncio
async def test_approvals_command_returns_fresh_actionable_links(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.approval_values = [approval(actionable=True)]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    await gateway._handle_update(
        {
            "message": {
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "/approvals",
            }
        }
    )

    assert len(telegram.sent) == 1
    assert telegram.sent[0][2]["button_text"] == "Review approval"


@pytest.mark.asyncio
async def test_approvals_command_returns_one_mission_plan_not_phase_approvals(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.mission_values = [
        {
            "id": "mission-1",
            "milestone_id": "M9-PILOT",
            "objective": "Run one bounded supervised mission.",
            "manifest_digest": "a" * 64,
            "supervision_status": "pending_approval",
            "supervision_policy": {"max_auto_recoveries": 2},
            "supervision_exception": {},
            "actionable": True,
        }
    ]
    channel.approval_values = [approval(actionable=False, suffix="02")]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    await gateway._send_approvals()

    assert len(telegram.sent) == 1
    assert "M9-PILOT" in telegram.sent[0][1]
    assert telegram.sent[0][2]["button_text"] == "Review mission plan"
