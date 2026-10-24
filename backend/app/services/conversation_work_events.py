from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ApprovalEvent,
    Artifact,
    FounderConversationEvent,
    FounderConversationMessage,
    FounderNotification,
    FounderProposal,
    Task,
    TaskApproval,
    TaskEvent,
)
from app.schemas.conversation import ConversationWorkEvent, ConversationWorkEventPage

SOURCE_ORDER = {
    "message": 10,
    "conversation_event": 20,
    "proposal": 30,
    "task": 40,
    "approval": 50,
    "approval_event": 60,
    "task_event": 70,
    "artifact": 80,
    "notification": 90,
}
TERMINAL_STATES = {"succeeded", "completed", "cancelled", "rejected", "consumed"}
FAILURE_STATES = {"failed", "expired", "revoked", "needs_attention"}


def _cursor(occurred_at: datetime, source_type: str, source_id: str) -> str:
    raw = json.dumps(
        [occurred_at.isoformat(), SOURCE_ORDER[source_type], source_id],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[str, int, str]:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(decoded, list) or len(decoded) != 3:
            raise ValueError
        return str(decoded[0]), int(decoded[1]), str(decoded[2])
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid conversation event cursor.") from exc


def _category(event_type: str, state: str, source_type: str) -> str:
    lowered = f"{event_type} {state}".lower()
    if state in FAILURE_STATES or any(word in lowered for word in ("fail", "error")):
        return "failure"
    if state in TERMINAL_STATES or any(word in lowered for word in ("complete", "terminal")):
        return "terminal"
    if source_type == "message":
        return "message"
    if source_type == "proposal":
        return "proposal"
    if source_type in {"approval", "approval_event"}:
        return "approval"
    if source_type == "artifact":
        return "evidence"
    if source_type == "notification":
        return "notification"
    if "clarif" in lowered:
        return "clarification"
    if source_type == "task_event" and any(
        word in lowered for word in ("lease", "claim", "heartbeat", "worker")
    ):
        return "worker"
    if source_type == "task_event" and any(
        word in lowered for word in ("tool", "progress", "result", "step", "artifact")
    ):
        return "tool"
    return "planning"


def _event(
    *,
    conversation_id: uuid.UUID,
    source_type: str,
    source_id: str,
    occurred_at: datetime,
    event_type: str,
    state: str,
    label: str,
    detail: str,
    payload: dict[str, Any] | None = None,
    task_id: uuid.UUID | None = None,
) -> ConversationWorkEvent:
    cursor = _cursor(occurred_at, source_type, source_id)
    return ConversationWorkEvent(
        id=f"{source_type}:{source_id}",
        cursor=cursor,
        conversation_id=conversation_id,
        task_id=task_id,
        category=_category(event_type, state, source_type),
        event_type=event_type,
        state=state,
        label=label,
        detail=detail,
        source_type=source_type,
        source_id=source_id,
        payload=payload or {},
        occurred_at=occurred_at,
    )


def conversation_work_events(
    db: Session,
    conversation_id: uuid.UUID,
    *,
    after: str | None = None,
    limit: int = 100,
) -> ConversationWorkEventPage:
    tasks = db.scalars(
        select(Task)
        .where(Task.conversation_id == conversation_id)
        .order_by(Task.created_at, Task.id)
    ).all()
    task_ids = [task.id for task in tasks]
    task_by_id = {task.id: task for task in tasks}
    events: list[ConversationWorkEvent] = []

    for message in db.scalars(
        select(FounderConversationMessage)
        .where(FounderConversationMessage.conversation_id == conversation_id)
        .order_by(FounderConversationMessage.sequence)
    ).all():
        events.append(_event(
            conversation_id=conversation_id, source_type="message", source_id=str(message.id),
            occurred_at=message.created_at, event_type="message_recorded", state="recorded",
            label=f"{message.role.title()} message",
            detail=f"{message.channel} message {message.sequence}",
            payload={"role": message.role, "channel": message.channel,
                     "channel_message_id": message.channel_message_id,
                     "reply_to_message_id": str(message.reply_to_message_id) if message.reply_to_message_id else None,
                     "content_digest": message.content_digest},
        ))
    for value in db.scalars(
        select(FounderConversationEvent)
        .where(FounderConversationEvent.conversation_id == conversation_id)
        .order_by(FounderConversationEvent.id)
    ).all():
        events.append(_event(
            conversation_id=conversation_id, source_type="conversation_event", source_id=str(value.id),
            occurred_at=value.created_at, event_type=value.event_type, state=value.resulting_status,
            label=value.event_type.replace("_", " ").title(), detail=f"Conversation revision {value.revision}",
            payload={"actor": value.actor, "prior_status": value.prior_status,
                     "revision": value.revision, **(value.payload or {})},
        ))
    for value in db.scalars(
        select(FounderProposal).where(FounderProposal.conversation_id == conversation_id)
    ).all():
        events.append(_event(
            conversation_id=conversation_id, source_type="proposal", source_id=str(value.id),
            occurred_at=value.created_at, event_type="proposal_recorded", state=value.status,
            label="Planner proposal", detail=(value.proposal or {}).get("summary", "Governed proposal"),
            payload={"proposal_digest": value.proposal_digest,
                     "conversation_revision": value.conversation_revision},
            task_id=value.source_task_id,
        ))
    for task in tasks:
        events.append(_event(
            conversation_id=conversation_id, source_type="task", source_id=str(task.id),
            occurred_at=task.created_at, event_type="task_recorded", state=task.status,
            label=task.task_number, detail=task.title,
            payload={"task_type": task.task_type, "plan_digest": task.plan_digest,
                     "attempt_count": task.attempt_count, "max_attempts": task.max_attempts},
            task_id=task.id,
        ))
    approvals = db.scalars(
        select(TaskApproval).where(TaskApproval.task_id.in_(task_ids))
    ).all() if task_ids else []
    approval_by_id = {approval.id: approval for approval in approvals}
    for value in approvals:
        task = task_by_id[value.task_id]
        events.append(_event(
            conversation_id=conversation_id, source_type="approval", source_id=str(value.id),
            occurred_at=value.created_at, event_type="approval_recorded", state=value.status,
            label="Approval gate", detail=f"{task.task_number} · risk {value.risk_level}",
            payload={"plan_digest": value.plan_digest, "risk_level": value.risk_level,
                     "scope": value.scope, "expires_at": value.expires_at.isoformat() if value.expires_at else None},
            task_id=value.task_id,
        ))
    if approval_by_id:
        for value in db.scalars(
            select(ApprovalEvent).where(ApprovalEvent.approval_id.in_(approval_by_id))
        ).all():
            approval = approval_by_id[value.approval_id]
            events.append(_event(
                conversation_id=conversation_id, source_type="approval_event", source_id=str(value.id),
                occurred_at=value.created_at, event_type=value.event_type,
                state=approval.status, label=value.event_type.replace("_", " ").title(),
                detail=value.reason or task_by_id[approval.task_id].task_number,
                payload={"approval_id": str(value.approval_id), "actor": value.actor, **(value.payload or {})},
                task_id=approval.task_id,
            ))
    if task_ids:
        for value in db.scalars(
            select(TaskEvent).where(TaskEvent.task_id.in_(task_ids))
        ).all():
            task = task_by_id[value.task_id]
            events.append(_event(
                conversation_id=conversation_id, source_type="task_event", source_id=str(value.id),
                occurred_at=value.created_at, event_type=value.event_type, state=task.status,
                label=value.event_type.replace("_", " ").title(), detail=value.message,
                payload={"attempt_number": value.attempt_number,
                         "agent_id": str(value.agent_id) if value.agent_id else None, **(value.payload or {})},
                task_id=value.task_id,
            ))
        for value in db.scalars(
            select(Artifact).where(Artifact.task_id.in_(task_ids))
        ).all():
            events.append(_event(
                conversation_id=conversation_id, source_type="artifact", source_id=str(value.id),
                occurred_at=value.created_at, event_type="artifact_registered", state=value.verification_status,
                label=value.name, detail=f"{value.artifact_type} · {value.size_bytes} bytes",
                payload={"sha256": value.sha256, "artifact_type": value.artifact_type,
                         "verification_status": value.verification_status, "location": value.location},
                task_id=value.task_id,
            ))
    notification_entities = {conversation_id, *task_ids, *approval_by_id}
    if notification_entities:
        for value in db.scalars(
            select(FounderNotification).where(
                FounderNotification.entity_id.in_(notification_entities)
            )
        ).all():
            approval = approval_by_id.get(value.entity_id)
            task_id = (
                approval.task_id
                if approval
                else value.entity_id if value.entity_id in task_by_id else None
            )
            events.append(_event(
                conversation_id=conversation_id, source_type="notification", source_id=str(value.id),
                occurred_at=value.created_at, event_type="notification_delivery", state=value.state,
                label="Telegram delivery", detail=f"{value.kind} · {value.state}",
                payload={"kind": value.kind, "acknowledged_by": value.acknowledged_by,
                         "acknowledged_at": value.acknowledged_at.isoformat() if value.acknowledged_at else None,
                         "deduplication_key": value.deduplication_key},
                task_id=task_id,
            ))

    events.sort(key=lambda item: (item.occurred_at, SOURCE_ORDER[item.source_type], item.source_id))
    high_watermark = events[-1].cursor if events else None
    if after:
        decoded = _decode_cursor(after)
        events = [item for item in events if (
            item.occurred_at.isoformat(), SOURCE_ORDER[item.source_type], item.source_id
        ) > decoded]
    page = events[:limit]
    return ConversationWorkEventPage(
        conversation_id=conversation_id,
        events=page,
        next_cursor=page[-1].cursor if page else after,
        has_more=len(events) > limit,
        high_watermark=high_watermark,
    )
