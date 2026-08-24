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
        self.conversation_values: list[dict] = []
        self.turns: list[tuple[str, dict]] = []
        self.proposal_decisions: list[tuple[str, str, str]] = []
        self.proposal_values: list[dict] = []
        self.approval_values: list[dict] = []
        self.mission_values: list[dict] = []
        self.mission_approvals: list[tuple[str, str]] = []
        self.note_values: list[dict] = []
        self.notification_values: list[dict] = []
        self.acknowledged: list[tuple[str, str]] = []

    async def create_request(self, payload):
        self.created.append(payload)
        return {"task_number": "FOUNDER-1"}

    async def create_conversation(self, payload):
        self.created.append(payload)
        conversation = {
            "id": "conversation-1",
            "short_id": "thread000001",
            "status": "collecting",
            "title": payload["title"],
            "project": "bulletproof_bt",
            "revision": 1,
            "current_specification": {},
            "messages": [{"role": "founder", "content": payload["message"]}],
        }
        self.conversation_values = [conversation]
        return {
            "conversation": conversation,
            "task_id": "task-1",
            "task_number": "FOUNDER-CONVERSATION-1",
        }

    async def add_conversation_turn(self, conversation_id, payload):
        self.turns.append((conversation_id, payload))
        conversation = self.conversation_values[0]
        conversation["revision"] += 1
        conversation["messages"].append(
            {"role": "founder", "content": payload["message"]}
        )
        return {
            "conversation": conversation,
            "task_id": f"task-{conversation['revision']}",
            "task_number": f"FOUNDER-CONVERSATION-{conversation['revision']}",
        }

    async def conversations(self, founder_key):
        return self.conversation_values

    async def active_conversation(self, founder_key):
        return self.conversation_values[0] if self.conversation_values else None

    async def transition_conversation(self, conversation_id, payload):
        conversation = self.conversation_values[0]
        conversation["status"] = {
            "finish": "finished",
            "stop": "stopped",
            "resume": "collecting",
        }[payload["action"]]
        return conversation

    async def proposals(self):
        return self.proposal_values

    async def tasks(self):
        return []

    async def approvals(self):
        return self.approval_values

    async def notifications(self):
        return self.notification_values

    async def acknowledge_notification(self, notification_id, delivery_reference):
        self.acknowledged.append((notification_id, delivery_reference))
        self.notification_values = [
            value
            for value in self.notification_values
            if value["id"] != notification_id
        ]
        return {}

    async def missions(self):
        return self.mission_values

    async def operational_notes(self, query=None):
        if not query:
            return self.note_values
        return [
            note
            for note in self.note_values
            if query.lower() in f"{note['note_key']} {note['subject']}".lower()
        ]

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


def approval_notification(suffix: str = "02") -> dict:
    value = approval(actionable=True, suffix=suffix)
    return {
        "id": f"notification-{suffix}",
        "kind": "approval_required",
        "payload": {
            "approval_id": value["id"],
            "task_number": value["task_number"],
            "task_title": value["task_title"],
            "operation": value["operation"],
            "task_type": value["scope"]["task_type"],
            "risk_level": value["risk_level"],
            "plan_digest": value["plan_digest"],
        },
    }


def clarification_proposal() -> dict:
    return {
        "id": "proposal-clarification",
        "status": "proposed",
        "proposal_digest": "c" * 64,
        "proposal": {
            "summary": "The research request needs immutable identifiers.",
            "recommended_action": "needs_clarification",
            "target_role": "research-experiment executor",
            "proposed_task": None,
            "clarification_questions": [
                "What base reference should be used?",
                "What hypothesis ID should identify the trial?",
            ],
        },
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
    assert channel.created[0]["founder_key"] == "founder:primary"
    assert channel.created[0]["channel"] == "telegram"
    assert channel.created[0]["message"].startswith("Please verify")


@pytest.mark.asyncio
async def test_august_23_followups_remain_one_conversation(tmp_path: Path) -> None:
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
    turns = [
        "Backtest whether an equity risk-off regime predicts BTC residual returns over one month.",
        "Choose the best options and select a random one month range.",
        "January to February 2022; use a stable universe and choose the best net-EV option.",
        "Do not ask for more clarification. Run the most reasonable test.",
        "Answer all remaining questions yourself and do the test.",
    ]

    for index, text in enumerate(turns, 1):
        await gateway._handle_update(
            {
                "message": {
                    "message_id": index,
                    "from": {"id": 123},
                    "chat": {"id": 456},
                    "text": text,
                }
            }
        )

    assert len(channel.created) == 1
    assert len(channel.turns) == 4
    assert {conversation_id for conversation_id, _ in channel.turns} == {
        "conversation-1"
    }
    assert channel.conversation_values[0]["revision"] == 5
    assert [
        message["content"] for message in channel.conversation_values[0]["messages"]
    ] == turns


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
async def test_clarification_proposal_sends_questions_without_approval_link(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.proposal_values = [clarification_proposal()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )

    await gateway._notify_proposals()

    assert len(telegram.sent) == 1
    message = telegram.sent[0][1]
    assert "Clarification required" in message
    assert "What base reference" in message
    assert "button_url" not in telegram.sent[0][2]


@pytest.mark.asyncio
async def test_stale_clarification_approval_token_cannot_materialize(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.proposal_values = [clarification_proposal()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    token = store.create("proposal", "proposal-clarification", "c" * 64, 300)
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )

    await gateway._decide_handoff(token, "approve")

    assert channel.proposal_decisions == []
    assert "clarification is required" in telegram.sent[0][1]
    assert store.resolve(token) is None


@pytest.mark.asyncio
async def test_notes_command_searches_operational_memory(tmp_path: Path) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.note_values = [
        {
            "note_key": "system-wide-storage-efficiency",
            "subject": "Audit system-wide storage efficiency",
            "status": "deferred",
            "urgency": "medium",
        }
    ]
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
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "/notes storage",
            }
        }
    )
    assert len(telegram.sent) == 1
    assert "system-wide-storage-efficiency" in telegram.sent[0][1]


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
async def test_outbox_notification_is_acknowledged_after_delivery(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.notification_values = [approval_notification()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    await gateway._notify_outbox()
    await gateway._notify_outbox()

    assert len(telegram.sent) == 1
    assert channel.acknowledged == [("notification-02", "telegram:456")]


@pytest.mark.asyncio
async def test_fleet_incident_uses_outbox_and_bounded_evidence(tmp_path: Path) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.notification_values = [
        {
            "id": "fleet-notification-1",
            "kind": "fleet_incident",
            "payload": {
                "incident_id": "incident-1",
                "machine": "vm2-deployment",
                "signal": "memory_pressure",
                "severity": "critical",
                "summary": "VM2 memory pressure is sustained",
                "evidence": {"value": 5.0, "threshold": 10.0},
            },
        }
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

    await gateway._notify_outbox()

    assert "Fleet critical" in telegram.sent[0][1]
    assert "vm2-deployment" in telegram.sent[0][1]
    assert len(telegram.sent[0][1]) < 500
    assert channel.acknowledged == [("fleet-notification-1", "telegram:456")]


@pytest.mark.asyncio
async def test_outbox_is_not_acknowledged_when_delivery_fails(
    tmp_path: Path,
) -> None:
    class FailingTelegram(Telegram):
        async def send(self, chat_id, text, **kwargs):
            raise RuntimeError("temporary delivery failure")

    telegram = FailingTelegram()
    channel = Channel()
    channel.notification_values = [approval_notification()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path),
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    await gateway.check()

    with pytest.raises(RuntimeError, match="temporary delivery failure"):
        await gateway._notify_outbox()

    assert channel.acknowledged == []


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
