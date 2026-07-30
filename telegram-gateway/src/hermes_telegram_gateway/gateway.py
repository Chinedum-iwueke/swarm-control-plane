from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

from .config import GatewaySettings
from .control_plane import FounderChannelClient
from .store import HandoffStore
from .telegram import TelegramClient


class RestrictedTelegramGateway:
    def __init__(
        self,
        settings: GatewaySettings,
        *,
        telegram: TelegramClient,
        channel: FounderChannelClient,
        store: HandoffStore,
    ) -> None:
        self._settings = settings
        self._telegram = telegram
        self._channel = channel
        self._store = store
        self._offset = 0
        self._username = ""

    async def check(self) -> None:
        identity = await self._telegram.get_me()
        self._username = identity["username"]
        await self._channel.proposals()

    async def run(self, stop: asyncio.Event) -> None:
        await self.check()
        while not stop.is_set():
            await self.run_once()

    async def run_once(self) -> None:
        updates, _, _, _ = await asyncio.gather(
            self._telegram.updates(
                self._offset, self._settings.poll_timeout_seconds
            ),
            self._notify_proposals(),
            self._notify_tasks(),
            self._notify_approvals(),
        )
        for update in updates:
            self._offset = max(self._offset, int(update["update_id"]) + 1)
            await self._handle_update(update)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        if (
            sender.get("id") != self._settings.founder_user_id
            or chat.get("id") != self._settings.founder_chat_id
        ):
            return
        text = str(message.get("text", "")).strip()
        if not text:
            return
        if text == "/status":
            await self._send_status()
            return
        if text == "/approvals":
            await self._send_approvals()
            return
        if text.startswith("/start review_"):
            await self._review_handoff(text.removeprefix("/start review_"))
            return
        if text.startswith("/approve "):
            await self._decide_handoff(
                text.removeprefix("/approve ").strip(), "approve"
            )
            return
        if text.startswith("/reject "):
            await self._decide_handoff(
                text.removeprefix("/reject ").strip(), "reject"
            )
            return
        if text.startswith("/"):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Supported: plain-English request, /status, /approvals, "
                "approval links.",
            )
            return
        project, risk = classify_request(text)
        result = await self._channel.create_request(
            {
                "kind": "task",
                "project": project,
                "title": title_for(text),
                "objective": text,
                "risk_level": risk,
                "acceptance_criteria": [],
            }
        )
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Request accepted: {result['task_number']}\n"
            "The planner will return a structured proposal for review.",
        )

    async def _notify_proposals(self) -> None:
        for item in await self._channel.proposals():
            digest = item["proposal_digest"]
            state = f"{item['status']}:{digest}"
            if not self._store.changed(f"proposal:{item['id']}", state):
                continue
            proposal = item["proposal"]
            if item["status"] == "proposed":
                token = self._store.create(
                    "proposal",
                    item["id"],
                    digest,
                    self._settings.handoff_ttl_seconds,
                )
                url = f"https://t.me/{self._username}?start=review_{token}"
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Proposal ready\n{proposal['summary']}\n"
                    f"Target: {proposal.get('target_role') or 'unassigned'}\n"
                    f"Action: {proposal['recommended_action']}\n"
                    f"Digest: {digest[:12]}",
                    button_text="Review proposal",
                    button_url=url,
                )
            else:
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Proposal {digest[:12]} is now {item['status']}.",
                )

    async def _notify_tasks(self) -> None:
        for task in await self._channel.tasks():
            state = f"{task['status']}:{task['attempt_count']}:{task['updated_at']}"
            if not self._store.changed(f"task:{task['id']}", _digest(state)):
                continue
            if task["status"] in {"succeeded", "failed"}:
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"{task['task_number']} · {task['status']}\n{task['title']}",
                )

    async def _notify_approvals(self) -> None:
        for approval in await self._channel.approvals():
            if approval["status"] != "pending" or not approval["actionable"]:
                continue
            state = (
                f"{approval['status']}:{approval['actionable']}:"
                f"{approval['plan_digest']}"
            )
            if not self._store.changed(f"approval:{approval['id']}", state):
                continue
            await self._send_approval(approval)

    async def _send_approvals(self) -> None:
        approvals = [
            item
            for item in await self._channel.approvals()
            if item["status"] == "pending" and item["actionable"]
        ]
        if not approvals:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "No approvals are actionable now.",
            )
            return
        for approval in approvals:
            await self._send_approval(approval)

    async def _send_approval(self, approval: dict[str, Any]) -> None:
        token = self._store.create(
            "approval",
            approval["id"],
            approval["plan_digest"],
            self._settings.handoff_ttl_seconds,
        )
        url = f"https://t.me/{self._username}?start=review_{token}"
        operation = approval.get("operation") or approval["scope"]["task_type"]
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Task approval required\n"
            f"{approval['task_number']} · {approval['task_title']}\n"
            f"Operation: {operation}\n"
            f"Risk: {approval['risk_level']}\n"
            f"Plan: {approval['plan_digest']}",
            button_text="Review approval",
            button_url=url,
        )

    async def _review_handoff(self, token: str) -> None:
        handoff = self._store.resolve(token)
        if handoff is None:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "This review link is invalid, expired, or already used.",
            )
            return
        kind, entity_id, expected_digest = handoff
        if kind == "approval":
            current = next(
                (
                    item
                    for item in await self._channel.approvals()
                    if item["id"] == entity_id
                ),
                None,
            )
            if (
                current is None
                or current["status"] != "pending"
                or not current["actionable"]
                or current["plan_digest"] != expected_digest
            ):
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Approval state changed. Open Mission Control for the latest record.",
                )
                return
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Approve {current['task_number']} · "
                f"{current['task_title']}?\n"
                f"Operation: {current.get('operation') or current['scope']['task_type']}\n"
                f"Risk: {current['risk_level']}\n"
                f"Plan: {expected_digest}\n\n"
                f"Approve: /approve {token}\nReject: /reject {token}",
            )
            return
        if kind != "proposal":
            return
        current = next(
            (
                item
                for item in await self._channel.proposals()
                if item["id"] == entity_id
            ),
            None,
        )
        if (
            current is None
            or current["status"] != "proposed"
            or current["proposal_digest"] != expected_digest
        ):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Proposal state changed. Open Mission Control for the latest record.",
            )
            return
        task = current["proposal"].get("proposed_task")
        detail = (
            f"\nTask: {task['task_type']} · risk {task['risk_level']}"
            if task
            else "\nNo executable task is proposed."
        )
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"{current['proposal']['summary']}{detail}\n"
            f"Digest: {expected_digest}\n\n"
            f"Approve: /approve {token}\nReject: /reject {token}",
        )

    async def _decide_handoff(self, token: str, action: str) -> None:
        handoff = self._store.resolve(token)
        if handoff is None:
            await self._telegram.send(
                self._settings.founder_chat_id, "Approval handoff is invalid."
            )
            return
        kind, entity_id, expected_digest = handoff
        if kind == "approval":
            approvals = await self._channel.approvals()
            current = next(
                (item for item in approvals if item["id"] == entity_id), None
            )
            if (
                current is None
                or current["status"] != "pending"
                or not current["actionable"]
                or current["plan_digest"] != expected_digest
            ):
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Approval digest or state no longer matches.",
                )
                return
            await self._channel.decide_approval(
                entity_id,
                action,
                f"Founder Telegram {action}d plan {expected_digest[:12]}.",
            )
            self._store.consume(token)
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Task approval {expected_digest[:12]} {action}d.",
            )
            return
        proposals = await self._channel.proposals()
        current = next((item for item in proposals if item["id"] == entity_id), None)
        if (
            kind != "proposal"
            or current is None
            or current["status"] != "proposed"
            or current["proposal_digest"] != expected_digest
        ):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Proposal digest or state no longer matches.",
            )
            return
        api_action = "materialize" if action == "approve" else "reject"
        await self._channel.decide_proposal(
            entity_id,
            api_action,
            f"Founder Telegram {action}d digest {expected_digest[:12]}.",
        )
        self._store.consume(token)
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Proposal {expected_digest[:12]} {action}d.",
        )

    async def _send_status(self) -> None:
        tasks = await self._channel.tasks()
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        rendered = ", ".join(
            f"{status}: {count}" for status, count in sorted(counts.items())
        )
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Hermes status\n{rendered or 'No tasks recorded.'}",
        )


def classify_request(text: str) -> tuple[str, int]:
    lowered = text.lower()
    if any(word in lowered for word in ("postgres", "redis", "docker", "backup", "restart", "certificate", "infrastructure")):
        return "swarm-control-plane", 3 if "restart" in lowered else 1
    if any(word in lowered for word in ("research", "hypothesis", "backtest", "strategy", "experiment")):
        return "bulletproof_bt", 1
    if any(word in lowered for word in ("knowledge", "second brain", "index", "document", "research intelligence")):
        return "knowledge", 0
    return "swarm-control-plane", 1


def title_for(text: str) -> str:
    words = re.sub(r"\\s+", " ", text).strip().split()
    return " ".join(words[:12])[:160]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
