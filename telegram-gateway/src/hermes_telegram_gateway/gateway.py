from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any

from .channel_security import prohibited_input_reason
from .config import GatewaySettings
from .control_plane import ChannelError, FounderChannelClient
from .store import HandoffStore
from .telegram import TelegramClient, TelegramError


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
        self._offset = store.polling_offset()
        self._username = ""

    async def check(self) -> None:
        identity = await self._telegram.get_me()
        self._username = identity["username"]
        await self._channel.proposals()

    async def run(self, stop: asyncio.Event) -> None:
        delay = self._settings.retry_initial_seconds
        checked = False
        while not stop.is_set():
            try:
                if not checked:
                    await self.check()
                    checked = True
                    print(json.dumps({"event": "telegram_gateway_ready"}), flush=True)
                await self.run_once()
                delay = self._settings.retry_initial_seconds
            except (TelegramError, ChannelError) as exc:
                if not exc.retryable:
                    raise
                print(
                    json.dumps(
                        {
                            "event": "telegram_gateway_dependency_retry",
                            "dependency": "telegram"
                            if isinstance(exc, TelegramError)
                            else "control-plane",
                            "error": type(exc).__name__,
                            "detail": str(exc),
                            "method": exc.method,
                            "status_code": exc.status_code,
                            "retry_seconds": delay,
                        }
                    ),
                    flush=True,
                )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, self._settings.retry_max_seconds)

    async def run_once(self) -> None:
        updates, _, _, _, _, _ = await asyncio.gather(
            self._telegram.updates(self._offset, self._settings.poll_timeout_seconds),
            self._notify_proposals(),
            self._notify_tasks(),
            self._notify_outbox(),
            self._notify_missions(),
            self._notify_research_cycles(),
        )
        for update in sorted(updates, key=lambda item: int(item["update_id"])):
            if int(update["update_id"]) < self._offset:
                continue
            await self._handle_update(update)
            self._offset = max(self._offset, int(update["update_id"]) + 1)
            self._store.commit_polling_offset(self._offset)

    async def _notify_outbox(self) -> None:
        for notification in await self._channel.notifications():
            notification_id = str(notification["id"])
            delivered = self._store.notification_delivery(notification_id)
            if delivered is not None:
                await self._channel.acknowledge_notification(
                    notification_id, delivered
                )
                continue
            payload = notification["payload"]
            kind = notification["kind"]
            if kind == "approval_required":
                token = self._store.create(
                    "approval",
                    payload["approval_id"],
                    payload["plan_digest"],
                    self._settings.handoff_ttl_seconds,
                )
                operation = payload.get("operation") or payload["task_type"]
                sent = await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Task approval required\n"
                    f"{payload['task_number']} · {payload['task_title']}\n"
                    f"Operation: {operation}\n"
                    f"Risk: {payload['risk_level']}\n"
                    f"Plan: {payload['plan_digest']}",
                    button_text="Review approval",
                    button_url=f"https://t.me/{self._username}?start=review_{token}",
                )
            elif kind == "mission_approval_required":
                token = self._store.create(
                    "mission",
                    payload["mission_id"],
                    payload["manifest_digest"],
                    self._settings.handoff_ttl_seconds,
                )
                sent = await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Mission plan approval required\n"
                    f"{payload['milestone_id']}\n{payload['objective']}\n"
                    f"Plan: {payload['manifest_digest']}",
                    button_text="Review mission plan",
                    button_url=f"https://t.me/{self._username}?start=review_{token}",
                )
            elif kind == "task_ready":
                sent = await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Task ready for execution\n"
                    f"{payload['task_number']} · {payload['task_title']}",
                )
            elif kind == "fleet_incident":
                evidence = payload.get("evidence") or {}
                detail = ", ".join(
                    f"{key}={value}" for key, value in sorted(evidence.items())
                )[:300]
                sent = await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Fleet {payload['severity']}\n"
                    f"{payload['machine']} · {payload['signal']}\n"
                    f"{payload['summary']}\n{detail}",
                )
            elif kind == "service_slo_alert":
                evidence = payload.get("evidence") or {}
                detail = ", ".join(
                    f"{key}={value}" for key, value in sorted(evidence.items())
                )[:300]
                sent = await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"Service SLO {payload['state']} · {payload['severity']}\n"
                    f"{payload['service_key']} · {payload['indicator']}\n"
                    f"Owner: {payload['owner']}\n{payload['summary']}\n{detail}",
                )
            else:
                continue
            message_ids = [
                str(item["message_id"])
                for item in sent or []
                if item.get("message_id") is not None
            ]
            delivery_reference = (
                f"telegram:{self._settings.founder_chat_id}:"
                f"{','.join(message_ids) or 'accepted'}"
            )
            self._store.mark_notification_delivered(
                notification_id, delivery_reference
            )
            await self._channel.acknowledge_notification(
                notification_id, delivery_reference
            )

    async def _handle_update(self, update: dict[str, Any]) -> None:
        edited = update.get("edited_message")
        message = update.get("message") or edited or {}
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        if (
            sender.get("id") != self._settings.founder_user_id
            or chat.get("id") != self._settings.founder_chat_id
        ):
            self._store.record_security_event(
                "spoofed_sender_rejected",
                {
                    "update_id": str(update.get("update_id", "unknown")),
                    "sender_match": sender.get("id") == self._settings.founder_user_id,
                    "chat_match": chat.get("id") == self._settings.founder_chat_id,
                },
            )
            return
        text = str(message.get("text", "")).strip()
        if not text:
            return
        reason = prohibited_input_reason(
            text, max_chars=self._settings.max_message_chars
        )
        if reason is not None:
            self._store.record_security_event(
                "prohibited_input_rejected",
                {
                    "reason": reason,
                    "update_id": str(update.get("update_id", "unknown")),
                    "message_chars": len(text),
                },
            )
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Hermes blocked this message before intake because it appears to "
                "contain a credential, private key, password, or exceeds the safe "
                "message size. The content was not sent to the planner or retained. "
                "Rotate any real credential you pasted, then restate the request "
                "without secret values.",
            )
            return
        if not self._store.admit_founder_message(
            limit=self._settings.rate_limit_messages,
            window_seconds=self._settings.rate_limit_window_seconds,
        ):
            self._store.record_security_event(
                "founder_flood_throttled",
                {"update_id": str(update.get("update_id", "unknown"))},
            )
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Hermes paused intake because the bounded founder-channel rate was "
                "exceeded. Wait one minute, then continue; no task was created for "
                "this message.",
            )
            return
        if edited is not None:
            message_id = str(message.get("message_id", "unknown"))
            state_key = f"telegram-edit:{message_id}"
            state_digest = _digest(text)
            if self._store.is_changed(state_key, state_digest):
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Edited messages do not rewrite an accepted Hermes turn. "
                    "Send the correction as a new reply in the same thread.",
                )
                self._store.mark_seen(state_key, state_digest)
            return
        if text == "/status":
            await self._send_status()
            return
        if text == "/approvals":
            await self._send_approvals()
            return
        if text == "/research":
            await self._send_research_status()
            return
        if text == "/notes" or text.startswith("/notes "):
            await self._send_notes(text.removeprefix("/notes").strip() or None)
            return
        if text == "/threads":
            await self._send_threads()
            return
        if text == "/context":
            await self._send_context()
            return
        if text == "/finish" or text == "/stop":
            await self._transition_active(text.removeprefix("/"))
            return
        if text.startswith("/resume "):
            await self._resume_thread(text.removeprefix("/resume ").strip())
            return
        if text.startswith("/switch "):
            await self._switch_thread(text.removeprefix("/switch ").strip())
            return
        if text == "/continue":
            await self._route_draft("continue")
            return
        if text == "/cancel":
            if self._store.pop_routing_draft() is None:
                await self._telegram.send(
                    self._settings.founder_chat_id, "No pending message to cancel."
                )
            else:
                await self._telegram.send(
                    self._settings.founder_chat_id, "Pending message discarded."
                )
            return
        if text == "/new" or text.startswith("/new "):
            title = text.removeprefix("/new").strip()
            if title.lower() == "thread":
                title = ""
            if self._store.get_value("pending-routing-draft") is not None:
                await self._route_draft("new", title=title)
                return
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"New thread ready{f': {title}' if title else ''}. Send the first request as your next message.",
            )
            self._store.set_value("pending-new-title", title or "New founder request")
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
            await self._decide_handoff(text.removeprefix("/reject ").strip(), "reject")
            return
        if text.startswith("/"):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Supported: plain-English request, /new, /continue, /cancel, "
                "/threads, /switch, /context, /finish, /stop, /resume, /status, "
                "/approvals, /research, /notes, approval links.",
            )
            return
        founder_key = self._founder_key
        pending_title = self._store.pop_value("pending-new-title")
        message_id = (
            str(message.get("message_id"))
            if message.get("message_id") is not None
            else None
        )
        reply = message.get("reply_to_message") or {}
        reply_message_id = (
            str(reply.get("message_id"))
            if reply.get("message_id") is not None
            else None
        )
        reply_conversation_id = (
            self._store.conversation_for_message(reply_message_id)
            if reply_message_id
            else None
        )
        research_cycle = (
            self._store.research_cycle_for_message(reply_message_id)
            if reply_message_id
            else None
        )
        embedded_cycle = _daily_research_context(text)
        if (
            reply_message_id
            and reply_conversation_id is None
            and research_cycle is None
        ):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "That reply target is not linked to a Hermes thread. Use /threads "
                "and /switch <short-id>, then send the correction again.",
            )
            return
        if research_cycle is None:
            research_cycle = embedded_cycle
        active = None
        if pending_title is None and research_cycle is None:
            active = await self._selected_conversation(reply_conversation_id)
        if (
            active is not None
            and reply_conversation_id is None
            and pending_title is None
            and research_cycle is None
            and not self._store.conversation_session_active(active["id"])
        ):
            self._store.hold_routing_draft(text, message_id)
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Is this part of {active['short_id']} · {active['title']}, or new work?\n"
                "/continue — add the held message to this thread\n"
                "/new [thread name] — start a new thread with it\n"
                "/cancel — discard it",
            )
            return
        if reply_conversation_id and active is None:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "That thread is no longer open. Use /resume <short-id> before replying.",
            )
            return
        if active is None:
            if research_cycle is not None and embedded_cycle is None:
                text = _research_follow_up(research_cycle, text)
            result = await self._channel.create_conversation(
                {
                    "founder_key": founder_key,
                    "channel": "telegram",
                    "title": pending_title
                    or _research_title(research_cycle)
                    or title_for(text),
                    "message": text,
                    "channel_message_id": message_id,
                }
            )
        else:
            result = await self._channel.add_conversation_turn(
                active["id"],
                {
                    "founder_key": founder_key,
                    "channel": "telegram",
                    "message": text,
                    "channel_message_id": message_id,
                    "reply_to_channel_message_id": reply_message_id,
                },
            )
        conversation = result["conversation"]
        self._store.activate_conversation(conversation["id"])
        if message_id:
            self._store.bind_message(message_id, conversation["id"])
        if research_cycle is not None:
            acknowledgement = (
                f"Research request linked · {conversation['short_id']} · "
                f"revision {conversation['revision']}\n"
                f"Question: {str(research_cycle.get('question_digest', ''))[:12]}\n"
                "I will treat your next messages as refinements to this research "
                "job until you finish or switch threads."
            )
        else:
            acknowledgement = (
                f"Turn accepted · {conversation['short_id']} · "
                f"revision {conversation['revision']}\n"
                f"{conversation['title']}\nThe planner will continue this thread."
            )
        sent = await self._telegram.send(
            self._settings.founder_chat_id,
            acknowledgement,
        )
        for sent_message in sent or []:
            sent_message_id = sent_message.get("message_id")
            if sent_message_id is not None:
                self._store.bind_message(str(sent_message_id), conversation["id"])

    @property
    def _founder_key(self) -> str:
        return "founder:primary"

    async def _send_threads(self) -> None:
        items = await self._channel.conversations(self._founder_key)
        if not items:
            await self._telegram.send(
                self._settings.founder_chat_id, "No conversation threads recorded."
            )
            return
        lines = ["Founder threads"]
        lines.extend(
            f"{item['short_id']} · {item['status']} · {item['title']}"
            for item in items[:10]
        )
        await self._telegram.send(self._settings.founder_chat_id, "\n".join(lines))

    async def _send_context(self) -> None:
        item = await self._selected_conversation()
        if item is None:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "No active thread. Use /new or send a request.",
            )
            return
        unresolved = (item.get("current_specification") or {}).get(
            "unresolved_fields"
        ) or []
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Active thread {item['short_id']} · {item['status']} · revision {item['revision']}\n"
            f"{item['title']}\nProject: {item.get('project') or 'unclassified'}\n"
            f"Unresolved: {', '.join(unresolved) if unresolved else 'none recorded'}",
        )

    async def _transition_active(self, action: str) -> None:
        item = await self._selected_conversation()
        if item is None:
            await self._telegram.send(
                self._settings.founder_chat_id, "No active thread."
            )
            return
        result = await self._channel.transition_conversation(
            item["id"],
            {
                "founder_key": self._founder_key,
                "action": action,
                "reason": f"Founder requested {action} from Telegram.",
            },
        )
        self._store.pop_value("selected-conversation-id")
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Thread {result['short_id']} is {result['status']}.",
        )

    async def _resume_thread(self, short_id: str) -> None:
        items = await self._channel.conversations(self._founder_key)
        item = next((value for value in items if value["short_id"] == short_id), None)
        if item is None:
            await self._telegram.send(
                self._settings.founder_chat_id, "Thread not found."
            )
            return
        result = await self._channel.transition_conversation(
            item["id"],
            {
                "founder_key": self._founder_key,
                "action": "resume",
                "reason": "Founder resumed thread from Telegram.",
            },
        )
        self._store.activate_conversation(result["id"])
        await self._telegram.send(
            self._settings.founder_chat_id, f"Thread {result['short_id']} resumed."
        )

    async def _switch_thread(self, short_id: str) -> None:
        items = await self._channel.conversations(self._founder_key)
        item = next((value for value in items if value["short_id"] == short_id), None)
        if item is None or item["status"] not in {
            "collecting",
            "needs_clarification",
            "ready_for_review",
            "attention_required",
        }:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "Open thread not found. Use /resume for a stopped or finished thread.",
            )
            return
        self._store.activate_conversation(item["id"])
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Switched to {item['short_id']} · {item['title']}",
        )

    async def _route_draft(self, choice: str, *, title: str = "") -> None:
        draft = self._store.pop_routing_draft()
        if draft is None:
            await self._telegram.send(
                self._settings.founder_chat_id, "No pending message to route."
            )
            return
        text = str(draft.get("text") or "").strip()
        message_id = draft.get("message_id")
        if not text:
            await self._telegram.send(
                self._settings.founder_chat_id, "The pending message was empty."
            )
            return
        if choice == "continue":
            active = await self._selected_conversation()
            if active is None:
                self._store.hold_routing_draft(text, message_id)
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "There is no open current thread. Use /new [thread name].",
                )
                return
            result = await self._channel.add_conversation_turn(
                active["id"],
                {
                    "founder_key": self._founder_key,
                    "channel": "telegram",
                    "message": text,
                    "channel_message_id": message_id,
                },
            )
        else:
            result = await self._channel.create_conversation(
                {
                    "founder_key": self._founder_key,
                    "channel": "telegram",
                    "title": title or title_for(text),
                    "message": text,
                    "channel_message_id": message_id,
                }
            )
        conversation = result["conversation"]
        self._store.activate_conversation(conversation["id"])
        if message_id:
            self._store.bind_message(str(message_id), conversation["id"])
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Message routed · {conversation['short_id']} · revision "
            f"{conversation['revision']}\n{conversation['title']}",
        )

    async def _selected_conversation(
        self, preferred_id: str | None = None
    ) -> dict[str, Any] | None:
        if preferred_id:
            items = await self._channel.conversations(self._founder_key)
            preferred = next(
                (value for value in items if value["id"] == preferred_id), None
            )
            if preferred is None:
                return None
            if preferred["status"] not in {
                "collecting",
                "needs_clarification",
                "ready_for_review",
                "attention_required",
            }:
                return None
            return preferred
        selected = self._store.get_value("selected-conversation-id")
        if selected:
            items = await self._channel.conversations(self._founder_key)
            item = next((value for value in items if value["id"] == selected), None)
            if item and item["status"] in {
                "collecting",
                "needs_clarification",
                "ready_for_review",
                "attention_required",
            }:
                return item
        return await self._channel.active_conversation(self._founder_key)

    async def _notify_proposals(self) -> None:
        for item in await self._channel.proposals():
            digest = item["proposal_digest"]
            state = f"{item['status']}:{digest}"
            state_key = f"proposal:{item['id']}"
            if not self._store.is_changed(state_key, state):
                continue
            proposal = item["proposal"]
            if item["status"] == "proposed":
                if proposal["recommended_action"] == "needs_clarification":
                    await self._send_thread_message(
                        item.get("conversation_id"),
                        f"Clarification required\n{proposal['summary']}\n\n"
                        f"{_clarification_text(proposal)}\n\n"
                        "Reply to this message with the answers, or switch to the "
                        "named thread first.",
                    )
                    self._store.mark_seen(state_key, state)
                    continue
                token = self._store.create(
                    "proposal",
                    item["id"],
                    digest,
                    self._settings.handoff_ttl_seconds,
                )
                url = f"https://t.me/{self._username}?start=review_{token}"
                await self._send_thread_message(
                    item.get("conversation_id"),
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
            self._store.mark_seen(state_key, state)

    async def _notify_tasks(self) -> None:
        for task in await self._channel.tasks():
            state = f"{task['status']}:{task['attempt_count']}:{task['updated_at']}"
            state_key = f"task:{task['id']}"
            state_digest = _digest(state)
            if not self._store.is_changed(state_key, state_digest):
                continue
            if task["status"] in {"succeeded", "failed"}:
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    f"{task['task_number']} · {task['status']}\n{task['title']}",
                )
            self._store.mark_seen(state_key, state_digest)

    async def _notify_approvals(self) -> None:
        for approval in await self._channel.approvals():
            if approval["status"] != "pending" or not approval["actionable"]:
                continue
            state = (
                f"{approval['status']}:{approval['actionable']}:"
                f"{approval['plan_digest']}"
            )
            state_key = f"approval:{approval['id']}"
            if not self._store.is_changed(state_key, state):
                continue
            await self._send_approval(approval)
            self._store.mark_seen(state_key, state)

    async def _notify_missions(self) -> None:
        for mission in await self._channel.missions():
            status = mission["supervision_status"]
            if status != "attention_required":
                continue
            state = f"{status}:{mission['manifest_digest']}:{mission['supervision_exception']}"
            state_key = f"mission:{mission['id']}"
            state_digest = _digest(state)
            if not self._store.is_changed(state_key, state_digest):
                continue
            exception = mission.get("supervision_exception") or {}
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Mission needs attention\n{mission['milestone_id']}\n"
                f"Checkpoint: {exception.get('task_number', 'unknown')}\n"
                f"Category: {exception.get('category', 'unknown')}",
            )
            self._store.mark_seen(state_key, state_digest)

    async def _notify_research_cycles(self) -> None:
        for cycle in await self._channel.research_cycles():
            if cycle["status"] not in {
                "awaiting_brief",
                "duplicate_avoided",
                "completed",
                "attention_required",
            }:
                continue
            state = f"{cycle['status']}:{cycle['question_digest']}"
            state_key = f"research-cycle:{cycle['id']}"
            state_digest = _digest(state)
            if not self._store.is_changed(state_key, state_digest):
                continue
            sent = await self._telegram.send(
                self._settings.founder_chat_id,
                f"Daily research · {cycle['status']}\n{cycle['question']}\n"
                f"Question: {cycle['question_digest'][:12]}",
            )
            context = {
                "id": cycle["id"],
                "question": cycle["question"],
                "question_digest": cycle["question_digest"],
                "status": cycle["status"],
            }
            for message in sent or []:
                if message.get("message_id") is not None:
                    self._store.bind_research_cycle(str(message["message_id"]), context)
            self._store.mark_seen(state_key, state_digest)

    async def _send_research_status(self) -> None:
        cycles = await self._channel.research_cycles()
        if not cycles:
            await self._telegram.send(
                self._settings.founder_chat_id, "No daily research cycles recorded."
            )
            return
        lines = ["Hermes daily research"]
        for cycle in cycles[:7]:
            lines.append(
                f"{cycle['cycle_date']} · {cycle['status']} · {cycle['question_key']}"
            )
        await self._telegram.send(self._settings.founder_chat_id, "\n".join(lines))

    async def _send_notes(self, query: str | None) -> None:
        notes = await self._channel.operational_notes(query)
        if not notes:
            await self._telegram.send(
                self._settings.founder_chat_id, "No matching operational notes."
            )
            return
        lines = ["Hermes operational notes"]
        for note in notes[:10]:
            lines.append(
                f"{note['note_key']} · {note['status']} · {note['urgency']}\n"
                f"{note['subject']}"
            )
        await self._telegram.send(self._settings.founder_chat_id, "\n".join(lines))

    async def _send_approvals(self) -> None:
        missions = [
            item
            for item in await self._channel.missions()
            if item["supervision_status"] == "pending_approval" and item["actionable"]
        ]
        approvals = [
            item
            for item in await self._channel.approvals()
            if item["status"] == "pending" and item["actionable"]
        ]
        if not approvals and not missions:
            await self._telegram.send(
                self._settings.founder_chat_id,
                "No approvals are actionable now.",
            )
            return
        for mission in missions:
            token = self._store.create(
                "mission",
                mission["id"],
                mission["manifest_digest"],
                self._settings.handoff_ttl_seconds,
            )
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Mission plan approval required\n"
                f"{mission['milestone_id']}\n{mission['objective']}\n"
                f"Plan: {mission['manifest_digest']}",
                button_text="Review mission plan",
                button_url=f"https://t.me/{self._username}?start=review_{token}",
            )
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
        if kind == "mission":
            current = next(
                (
                    item
                    for item in await self._channel.missions()
                    if item["id"] == entity_id
                ),
                None,
            )
            if (
                current is None
                or current["supervision_status"] != "pending_approval"
                or current["manifest_digest"] != expected_digest
            ):
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Mission plan digest or state no longer matches.",
                )
                return
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Approve autonomous supervision for {current['milestone_id']}?\n"
                f"Plan: {expected_digest}\n"
                f"Recovery limit: {current['supervision_policy'].get('max_auto_recoveries', 0)}\n\n"
                f"Approve: /approve {token}\nReject in Mission Control.",
            )
            return
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
        if current.get("conversation_id"):
            self._store.set_value(
                "selected-conversation-id", current["conversation_id"]
            )
        task = current["proposal"].get("proposed_task")
        if task is None:
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"This proposal cannot be approved yet.\n\n"
                f"{_clarification_text(current['proposal'])}\n\n"
                "Reply in this thread with the requested answers.",
            )
            return
        detail = f"\nTask: {task['task_type']} · risk {task['risk_level']}"
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
        if kind == "mission":
            if action != "approve":
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Reject supervised missions in Mission Control with a recorded reason.",
                )
                return
            current = next(
                (
                    item
                    for item in await self._channel.missions()
                    if item["id"] == entity_id
                ),
                None,
            )
            if (
                current is None
                or current["supervision_status"] != "pending_approval"
                or current["manifest_digest"] != expected_digest
            ):
                await self._telegram.send(
                    self._settings.founder_chat_id,
                    "Mission plan digest or state no longer matches.",
                )
                return
            await self._channel.approve_mission(
                entity_id,
                f"Founder Telegram approved mission plan {expected_digest[:12]}.",
            )
            self._store.consume(token)
            await self._telegram.send(
                self._settings.founder_chat_id,
                f"Mission {current['milestone_id']} is now autonomously supervised.",
            )
            return
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
        conversation_id = current.get("conversation_id")
        if action == "approve" and current["proposal"].get("proposed_task") is None:
            self._store.consume(token)
            await self._telegram.send(
                self._settings.founder_chat_id,
                "This proposal cannot be approved because clarification is required.\n\n"
                f"{_clarification_text(current['proposal'])}\n\n"
                "Reply in this thread with the requested answers.",
            )
            return
        if (
            conversation_id
            and self._store.get_value("selected-conversation-id") != conversation_id
        ):
            await self._telegram.send(
                self._settings.founder_chat_id,
                "This proposal belongs to a different founder thread. Switch to that "
                "thread, reopen this review link, and verify the digest again.",
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
        tasks, missions = await asyncio.gather(
            self._channel.tasks(), self._channel.missions()
        )
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        rendered = ", ".join(
            f"{status}: {count}" for status, count in sorted(counts.items())
        )
        security_counts = self._store.security_event_counts()
        security = ", ".join(
            f"{key}: {value}" for key, value in sorted(security_counts.items())
        ) or "none"
        await self._telegram.send(
            self._settings.founder_chat_id,
            f"Hermes status\n{rendered or 'No tasks recorded.'}\n"
            f"Supervised missions: {sum(item['supervision_status'] == 'active' for item in missions)} active, "
            f"{sum(item['supervision_status'] == 'attention_required' for item in missions)} need attention\n"
            f"Channel security events: {security}",
        )

    async def _send_thread_message(
        self,
        conversation_id: str | None,
        text: str,
        *,
        button_text: str | None = None,
        button_url: str | None = None,
    ) -> None:
        sent = await self._telegram.send(
            self._settings.founder_chat_id,
            text,
            button_text=button_text,
            button_url=button_url,
        )
        if conversation_id:
            for message in sent or []:
                message_id = message.get("message_id")
                if message_id is not None:
                    self._store.bind_message(str(message_id), conversation_id)


def classify_request(text: str) -> tuple[str, int]:
    lowered = text.lower()
    if any(
        word in lowered
        for word in (
            "postgres",
            "redis",
            "docker",
            "backup",
            "restart",
            "certificate",
            "infrastructure",
        )
    ):
        return "swarm-control-plane", 3 if "restart" in lowered else 1
    if any(
        word in lowered
        for word in ("research", "hypothesis", "backtest", "strategy", "experiment")
    ):
        return "bulletproof_bt", 1
    if any(
        word in lowered
        for word in (
            "knowledge",
            "second brain",
            "index",
            "document",
            "research intelligence",
        )
    ):
        return "knowledge", 0
    return "swarm-control-plane", 1


def _clarification_text(proposal: dict) -> str:
    questions = proposal.get("clarification_questions") or []
    fields = proposal.get("unresolved_fields") or []
    formats = proposal.get("specification_format") or {}
    if not questions:
        return (
            "Questions:\n1. Provide the missing information requested by the planner."
        )
    rendered_items = []
    for index, question in enumerate(questions[:10], start=1):
        field = fields[index - 1] if index <= len(fields) else None
        label = f"`{field}` — " if field else ""
        guidance = f"\n   Format: {formats[field]}" if field in formats else ""
        rendered_items.append(f"{index}. {label}{str(question)[:500]}{guidance}")
    rendered = "\n".join(rendered_items)
    return f"Questions:\n{rendered}"


def title_for(text: str) -> str:
    words = re.sub(r"\\s+", " ", text).strip().split()
    return " ".join(words[:12])[:160]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _daily_research_context(text: str) -> dict[str, str] | None:
    match = re.search(
        r"Daily research\s*[\u00b7-]\s*(?P<status>[a-z_]+)\s*\n"
        r"(?P<question>[^\n]+)\s*\nQuestion:\s*(?P<digest>[0-9a-f]{12,64})",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return {
        "question": match.group("question").strip(),
        "question_digest": match.group("digest").lower(),
        "status": match.group("status").lower(),
    }


def _research_title(cycle: dict[str, Any] | None) -> str | None:
    if cycle is None:
        return None
    question = str(cycle.get("question") or "").strip()
    return f"Daily research: {question}"[:160] if question else "Daily research"


def _research_follow_up(cycle: dict[str, Any], text: str) -> str:
    return (
        f"Daily research · {cycle.get('status', 'awaiting_brief')}\n"
        f"{cycle.get('question', '')}\n"
        f"Question: {str(cycle.get('question_digest', ''))[:12]}\n\n"
        f"Founder request:\n{text}"
    )
