from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from hermes_telegram_gateway.config import GatewaySettings
from hermes_telegram_gateway.gateway import (
    RestrictedTelegramGateway,
    classify_request,
)
from hermes_telegram_gateway.store import HandoffStore
from hermes_telegram_gateway.telegram import TelegramError


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
        self.update_values: list[dict] = []
        self.offsets: list[int] = []

    async def get_me(self):
        return {"username": "hermes_test_bot"}

    async def updates(self, offset, *_):
        self.offsets.append(offset)
        return [
            value for value in self.update_values if int(value["update_id"]) >= offset
        ]

    async def send(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return [{"message_id": 10_000 + len(self.sent)}]


class TransientTelegram(Telegram):
    def __init__(self) -> None:
        super().__init__()
        self.update_calls = 0

    async def updates(self, offset, *_):
        self.update_calls += 1
        if self.update_calls == 1:
            raise TelegramError(
                "Telegram is unavailable.", retryable=True, method="getUpdates"
            )
        return []


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
        self.research_cycle_values: list[dict] = []
        self.acknowledged: list[tuple[str, str]] = []

    async def create_request(self, payload):
        self.created.append(payload)
        return {"task_number": "FOUNDER-1"}

    async def create_conversation(self, payload):
        self.created.append(payload)
        number = len(self.conversation_values) + 1
        conversation = {
            "id": f"conversation-{number}",
            "short_id": f"thread{number:06d}",
            "status": "collecting",
            "title": payload["title"],
            "project": "bulletproof_bt",
            "revision": 1,
            "current_specification": {},
            "messages": [{"role": "founder", "content": payload["message"]}],
        }
        self.conversation_values.insert(0, conversation)
        return {
            "conversation": conversation,
            "task_id": "task-1",
            "task_number": "FOUNDER-CONVERSATION-1",
        }

    async def add_conversation_turn(self, conversation_id, payload):
        self.turns.append((conversation_id, payload))
        conversation = next(
            value
            for value in self.conversation_values
            if value["id"] == conversation_id
        )
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
        return next(
            (
                value
                for value in self.conversation_values
                if value["status"]
                in {
                    "collecting",
                    "needs_clarification",
                    "ready_for_review",
                    "attention_required",
                }
            ),
            None,
        )

    async def transition_conversation(self, conversation_id, payload):
        conversation = next(
            value
            for value in self.conversation_values
            if value["id"] == conversation_id
        )
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

    async def research_cycles(self):
        return self.research_cycle_values

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

    async def decide_approval(self, approval_id, action, reason):
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
        "conversation_id": "conversation-1",
        "proposal": {
            "summary": "The research request needs immutable identifiers.",
            "recommended_action": "needs_clarification",
            "target_role": "research-experiment executor",
            "proposed_task": None,
            "clarification_questions": [
                "What base reference should be used?",
                "What hypothesis ID should identify the trial?",
            ],
            "unresolved_fields": ["base_ref", "hypothesis_id"],
            "specification_format": {
                "base_ref": "Git ref, for example main",
                "hypothesis_id": "Safe identifier, for example HERMES-BTC-H1",
            },
        },
    }


def executable_proposal() -> dict:
    return {
        "id": "proposal-executable",
        "status": "proposed",
        "proposal_digest": "e" * 64,
        "conversation_id": "conversation-1",
        "proposal": {
            "summary": "Run one bounded research experiment.",
            "recommended_action": "create_task",
            "target_role": "research runner",
            "proposed_task": {
                "task_type": "research_experiment",
                "risk_level": 1,
            },
            "clarification_questions": [],
            "unresolved_fields": [],
            "specification_format": {},
        },
    }


@pytest.mark.asyncio
async def test_daemon_retries_transient_telegram_failure_without_exiting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    telegram = TransientTelegram()
    channel = Channel()
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    configured = settings(tmp_path).model_copy(
        update={"retry_initial_seconds": 0.01, "retry_max_seconds": 0.02}
    )
    gateway = RestrictedTelegramGateway(
        configured,
        telegram=telegram,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        store=store,
    )
    stop = asyncio.Event()
    task = asyncio.create_task(gateway.run(stop))
    await asyncio.sleep(0.04)
    stop.set()
    await task

    assert telegram.update_calls >= 2
    output = capsys.readouterr().out
    assert "telegram_gateway_ready" in output
    assert "telegram_gateway_dependency_retry" in output


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


def test_polling_offset_and_message_binding_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "gateway.sqlite3"
    first = HandoffStore(path)
    first.initialize()
    first.commit_polling_offset(42)
    first.bind_message("telegram-message-7", "conversation-7")

    restarted = HandoffStore(path)
    restarted.initialize()

    assert restarted.polling_offset() == 42
    assert restarted.conversation_for_message("telegram-message-7") == "conversation-7"
    with pytest.raises(ValueError, match="cannot move backwards"):
        restarted.commit_polling_offset(41)


@pytest.mark.asyncio
async def test_run_once_commits_sorted_updates_only_after_acceptance(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    telegram.update_values = [
        {
            "update_id": 12,
            "message": {
                "message_id": 2,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Use January 2022.",
            },
        },
        {
            "update_id": 11,
            "message": {
                "message_id": 1,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Run a bounded BTC research experiment.",
            },
        },
    ]
    channel = Channel()
    path = tmp_path / "gateway.sqlite3"
    store = HandoffStore(path)
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    await gateway.run_once()

    assert store.polling_offset() == 13
    assert channel.created[0]["message"].startswith("Run a bounded")
    assert channel.turns[0][1]["message"] == "Use January 2022."
    restarted = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    await restarted.run_once()
    assert telegram.offsets[-1] == 13
    assert len(channel.turns) == 1


@pytest.mark.asyncio
async def test_failed_update_does_not_advance_durable_offset(tmp_path: Path) -> None:
    class FailingChannel(Channel):
        async def create_conversation(self, payload):
            raise RuntimeError("control plane unavailable")

    telegram = Telegram()
    telegram.update_values = [
        {
            "update_id": 21,
            "message": {
                "message_id": 1,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Start a research job.",
            },
        }
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=FailingChannel(), store=store
    )

    with pytest.raises(RuntimeError, match="control plane unavailable"):
        await gateway.run_once()

    assert store.polling_offset() == 0


@pytest.mark.asyncio
async def test_duplicate_update_id_is_handled_once(tmp_path: Path) -> None:
    update = {
        "update_id": 31,
        "message": {
            "message_id": 1,
            "from": {"id": 123},
            "chat": {"id": 456},
            "text": "Start one bounded research job.",
        },
    }
    telegram = Telegram()
    telegram.update_values = [update, update]
    channel = Channel()
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    await gateway.run_once()

    assert len(channel.created) == 1
    assert channel.turns == []
    assert store.polling_offset() == 32


@pytest.mark.asyncio
async def test_reply_to_prior_message_overrides_selected_thread(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    base = {
        "from": {"id": 123},
        "chat": {"id": 456},
    }
    await gateway._handle_update(
        {"message": {**base, "message_id": 1, "text": "First research job."}}
    )
    await gateway._handle_update(
        {"message": {**base, "message_id": 2, "text": "/new Infrastructure"}}
    )
    await gateway._handle_update(
        {"message": {**base, "message_id": 3, "text": "Second job."}}
    )
    assert store.get_value("selected-conversation-id") == "conversation-2"

    await gateway._handle_update(
        {
            "message": {
                **base,
                "message_id": 4,
                "text": "Continue the first job.",
                "reply_to_message": {"message_id": 1},
            }
        }
    )

    assert channel.turns[-1][0] == "conversation-1"
    assert channel.turns[-1][1]["reply_to_channel_message_id"] == "1"
    assert store.get_value("selected-conversation-id") == "conversation-1"


@pytest.mark.asyncio
async def test_daily_research_reply_starts_a_grounded_research_thread(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.conversation_values = [
        {
            "id": "conversation-old",
            "short_id": "oldthread0001",
            "status": "collecting",
            "title": "Prior work",
            "project": "swarm-control-plane",
            "revision": 1,
            "current_specification": {},
            "messages": [],
        }
    ]
    channel.research_cycle_values = [
        {
            "id": "cycle-1",
            "status": "awaiting_brief",
            "question": "Do equity shocks predict next-day BTC returns?",
            "question_digest": "23f98fe93e01" + "0" * 52,
        }
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    store.set_value("selected-conversation-id", "conversation-old")
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    await gateway._notify_research_cycles()
    await gateway._handle_update(
        {
            "message": {
                "message_id": 88,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Run the backtest and summarize it. Use one month only.",
                "reply_to_message": {"message_id": 10001},
            }
        }
    )

    created = channel.created[-1]
    assert created["title"].startswith("Daily research:")
    assert "23f98fe93e01" in created["message"]
    assert "Use one month only" in created["message"]
    assert channel.turns == []
    assert "Research request linked" in telegram.sent[-1][1]
    assert "next messages as refinements" in telegram.sent[-1][1]


@pytest.mark.asyncio
async def test_pasted_daily_research_card_does_not_pollute_selected_thread(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.conversation_values = [
        {
            "id": "conversation-old",
            "short_id": "oldthread0001",
            "status": "collecting",
            "title": "Prior work",
            "project": "swarm-control-plane",
            "revision": 1,
            "current_specification": {},
            "messages": [],
        }
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    store.set_value("selected-conversation-id", "conversation-old")
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    text = "Daily research · awaiting_brief\nDo equity shocks predict next-day BTC returns?\nQuestion: 23f98fe93e01\n\nRun the backtest and summarize it. Short run one month only."

    await gateway._handle_update(
        {
            "message": {
                "message_id": 89,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": text,
            }
        }
    )

    assert channel.created[-1]["message"] == text
    assert channel.created[-1]["title"].startswith("Daily research:")
    assert channel.turns == []


@pytest.mark.asyncio
async def test_ambiguous_plain_message_is_held_until_continue(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.conversation_values = [
        {
            "id": "conversation-old",
            "short_id": "oldthread0001",
            "status": "collecting",
            "title": "Existing work",
            "project": "swarm-control-plane",
            "revision": 1,
            "current_specification": {},
            "messages": [],
        }
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    store.set_value("selected-conversation-id", "conversation-old")
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    base = {"from": {"id": 123}, "chat": {"id": 456}}

    await gateway._handle_update(
        {
            "message": {
                **base,
                "message_id": 90,
                "text": "Do something Hermes has never seen before.",
            }
        }
    )

    assert channel.turns == []
    assert "or new work?" in telegram.sent[-1][1]
    await gateway._handle_update(
        {"message": {**base, "message_id": 91, "text": "/continue"}}
    )
    assert (
        channel.turns[-1][1]["message"] == "Do something Hermes has never seen before."
    )


@pytest.mark.asyncio
async def test_new_routes_held_message_without_retyping_it(tmp_path: Path) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.conversation_values = [
        {
            "id": "conversation-old",
            "short_id": "oldthread0001",
            "status": "collecting",
            "title": "Existing work",
            "project": "swarm-control-plane",
            "revision": 1,
            "current_specification": {},
            "messages": [],
        }
    ]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    store.set_value("selected-conversation-id", "conversation-old")
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    base = {"from": {"id": 123}, "chat": {"id": 456}}

    await gateway._handle_update(
        {
            "message": {
                **base,
                "message_id": 92,
                "text": "Explore a completely new operational idea.",
            }
        }
    )
    await gateway._handle_update(
        {"message": {**base, "message_id": 93, "text": "/new Novel operation"}}
    )

    assert channel.created[-1]["title"] == "Novel operation"
    assert (
        channel.created[-1]["message"] == "Explore a completely new operational idea."
    )
    assert channel.turns == []


@pytest.mark.asyncio
async def test_edited_message_never_rewrites_an_accepted_turn(tmp_path: Path) -> None:
    telegram = Telegram()
    channel = Channel()
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )
    update = {
        "edited_message": {
            "message_id": 7,
            "from": {"id": 123},
            "chat": {"id": 456},
            "text": "Changed instruction",
        }
    }

    await gateway._handle_update(update)
    await gateway._handle_update(update)

    assert channel.created == []
    assert channel.turns == []
    assert len(telegram.sent) == 1
    assert "do not rewrite" in telegram.sent[0][1]


@pytest.mark.asyncio
async def test_clarification_notification_reply_is_bound_to_its_thread(
    tmp_path: Path,
) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.conversation_values = [
        {
            "id": "conversation-1",
            "short_id": "thread000001",
            "status": "needs_clarification",
            "title": "Research",
            "project": "bulletproof_bt",
            "revision": 1,
            "current_specification": {},
            "messages": [],
        }
    ]
    channel.proposal_values = [clarification_proposal()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    await gateway._notify_proposals()
    notification_id = telegram.sent[0][2]
    assert store.conversation_for_message("10001") == "conversation-1"
    await gateway._handle_update(
        {
            "message": {
                "message_id": 88,
                "from": {"id": 123},
                "chat": {"id": 456},
                "text": "Use main and the generated hypothesis ID.",
                "reply_to_message": {"message_id": 10001},
            }
        }
    )

    assert notification_id["button_url"] is None
    assert channel.turns[-1][0] == "conversation-1"


@pytest.mark.asyncio
async def test_wrong_thread_proposal_cannot_be_approved(tmp_path: Path) -> None:
    telegram = Telegram()
    channel = Channel()
    channel.proposal_values = [executable_proposal()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    store.set_value("selected-conversation-id", "conversation-2")
    token = store.create("proposal", "proposal-executable", "e" * 64, 300)
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    await gateway._decide_handoff(token, "approve")

    assert channel.proposal_decisions == []
    assert store.resolve(token) is not None
    assert "different founder thread" in telegram.sent[-1][1]


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
    assert telegram.sent[0][2]["button_url"] is None


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
async def test_failed_proposal_notification_is_retried(tmp_path: Path) -> None:
    class RecoveringTelegram(Telegram):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        async def send(self, chat_id, text, **kwargs):
            if self.fail:
                raise RuntimeError("temporary delivery failure")
            return await super().send(chat_id, text, **kwargs)

    telegram = RecoveringTelegram()
    channel = Channel()
    channel.proposal_values = [executable_proposal()]
    store = HandoffStore(tmp_path / "gateway.sqlite3")
    store.initialize()
    gateway = RestrictedTelegramGateway(
        settings(tmp_path), telegram=telegram, channel=channel, store=store
    )

    with pytest.raises(RuntimeError, match="temporary delivery failure"):
        await gateway._notify_proposals()
    telegram.fail = False
    await gateway._notify_proposals()

    assert len(telegram.sent) == 1
    assert "Proposal ready" in telegram.sent[0][1]


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
