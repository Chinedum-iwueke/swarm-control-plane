from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    FounderConversation,
    FounderConversationEvent,
    FounderConversationMessage,
    Task,
)
from app.schemas import ConversationCreate, ConversationTurnCreate, TaskCreate
from app.services.tasks import append_task_event, build_task, persist_new_task

OPEN_STATUSES = {
    "collecting",
    "planning",
    "needs_clarification",
    "ready_for_review",
    "attention_required",
}
RESEARCH_WORDS = {
    "research",
    "hypothesis",
    "backtest",
    "strategy",
    "experiment",
    "sharpe",
    "drawdown",
}
INFRA_WORDS = {
    "postgres",
    "redis",
    "docker",
    "backup",
    "restart",
    "certificate",
    "infrastructure",
}
KNOWLEDGE_WORDS = {
    "knowledge",
    "second brain",
    "index",
    "document",
    "research intelligence",
}


def create_conversation(
    db: Session, payload: ConversationCreate
) -> tuple[FounderConversation, Task]:
    conversation = FounderConversation(
        short_id=uuid.uuid4().hex[:12],
        founder_key=payload.founder_key,
        title=payload.title,
        status="collecting",
        working_summary="",
        current_specification={},
        revision=0,
    )
    db.add(conversation)
    db.flush()
    task = append_turn(
        db,
        conversation,
        ConversationTurnCreate(
            founder_key=payload.founder_key,
            channel=payload.channel,
            message=payload.message,
            channel_message_id=payload.channel_message_id,
            reply_to_channel_message_id=payload.reply_to_channel_message_id,
        ),
    )
    _event(
        db,
        conversation,
        "conversation_created",
        payload.founder_key,
        None,
        {"channel": payload.channel},
    )
    return conversation, task


def append_turn(
    db: Session, conversation: FounderConversation, payload: ConversationTurnCreate
) -> Task:
    if conversation.founder_key != payload.founder_key:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=409, detail="Conversation is not open for new turns."
        )
    duplicate = None
    if payload.channel_message_id:
        duplicate = db.scalar(
            select(FounderConversationMessage).where(
                FounderConversationMessage.conversation_id == conversation.id,
                FounderConversationMessage.channel_message_id
                == payload.channel_message_id,
            )
        )
    if duplicate is not None:
        task = db.scalar(
            select(Task)
            .where(
                Task.conversation_id == conversation.id,
                Task.conversation_revision == conversation.revision,
            )
            .order_by(Task.created_at.desc())
        )
        if task is None:
            raise HTTPException(status_code=409, detail="Duplicate turn has no task.")
        return task
    sequence = (
        int(
            db.scalar(
                select(
                    func.coalesce(func.max(FounderConversationMessage.sequence), 0)
                ).where(FounderConversationMessage.conversation_id == conversation.id)
            )
            or 0
        )
        + 1
    )
    digest = hashlib.sha256(payload.message.encode()).hexdigest()
    reply_to = None
    if payload.reply_to_channel_message_id:
        reply_to = db.scalar(
            select(FounderConversationMessage).where(
                FounderConversationMessage.conversation_id == conversation.id,
                FounderConversationMessage.channel == payload.channel,
                FounderConversationMessage.channel_message_id
                == payload.reply_to_channel_message_id,
            )
        )
    message = FounderConversationMessage(
        conversation_id=conversation.id,
        sequence=sequence,
        role="founder",
        channel=payload.channel,
        channel_message_id=payload.channel_message_id,
        reply_to_message_id=reply_to.id if reply_to else None,
        content=payload.message,
        content_digest=digest,
        detail={"reply_to_channel_message_id": payload.reply_to_channel_message_id}
        if payload.reply_to_channel_message_id
        else {},
    )
    db.add(message)
    # Production sessions disable autoflush; persist the turn before deriving context.
    db.flush()
    conversation.revision += 1
    stale_tasks = db.scalars(
        select(Task).where(
            Task.conversation_id == conversation.id,
            Task.conversation_revision < conversation.revision,
            Task.status == "queued",
        )
    ).all()
    for stale_task in stale_tasks:
        stale_task.status = "cancelled"
        append_task_event(
            db,
            stale_task,
            "conversation_revision_superseded",
            "A newer founder turn superseded this planning revision.",
            payload={"superseded_by_revision": conversation.revision},
        )
    messages = _founder_messages(db, conversation.id)
    conversation.project = _classify_project(messages)
    conversation.working_summary = _bounded_summary(messages)
    prior = conversation.status
    conversation.status = "collecting"
    conversation.current_specification = {}
    conversation.specification_digest = None
    task = _planning_task(db, conversation, messages, payload.founder_key)
    persist_new_task(db, task)
    _event(
        db,
        conversation,
        "founder_turn_added",
        payload.founder_key,
        prior,
        {"message_digest": digest, "task_id": str(task.id), "sequence": sequence},
    )
    return task


def transition_conversation(
    db: Session,
    conversation: FounderConversation,
    *,
    action: str,
    actor: str,
    reason: str,
) -> None:
    targets = {
        "finish": "finished",
        "stop": "stopped",
        "archive": "archived",
        "resume": "collecting",
    }
    target = targets[action]
    if action == "resume" and conversation.status not in {"finished", "stopped"}:
        raise HTTPException(
            status_code=409, detail="Only finished or stopped conversations may resume."
        )
    if action != "resume" and conversation.status in {"archived", "stopped"}:
        raise HTTPException(
            status_code=409, detail="Conversation transition is invalid."
        )
    prior = conversation.status
    conversation.status = target
    conversation.closed_at = None if target == "collecting" else datetime.now(UTC)
    _event(db, conversation, f"conversation_{action}", actor, prior, {"reason": reason})


def record_planner_response(
    db: Session, task: Task, proposal: dict, digest: str
) -> None:
    if task.conversation_id is None:
        return
    conversation = db.scalar(
        select(FounderConversation)
        .where(FounderConversation.id == task.conversation_id)
        .with_for_update()
    )
    if conversation is None or task.conversation_revision != conversation.revision:
        return
    action = proposal["recommended_action"]
    target = {
        "create_task": "ready_for_review",
        "needs_clarification": "needs_clarification",
        "decline": "attention_required",
        "respond": "collecting",
    }[action]
    prior = conversation.status
    conversation.status = target
    conversation.current_specification = proposal
    conversation.specification_digest = digest
    sequence = (
        int(
            db.scalar(
                select(
                    func.coalesce(func.max(FounderConversationMessage.sequence), 0)
                ).where(FounderConversationMessage.conversation_id == conversation.id)
            )
            or 0
        )
        + 1
    )
    content = proposal["summary"]
    questions = proposal.get("clarification_questions") or []
    if questions:
        content += "\n\n" + "\n".join(
            f"{index}. {question}" for index, question in enumerate(questions, 1)
        )
    db.add(
        FounderConversationMessage(
            conversation_id=conversation.id,
            sequence=sequence,
            role="hermes",
            channel="system",
            content=content,
            content_digest=hashlib.sha256(content.encode()).hexdigest(),
            detail={"proposal_digest": digest, "recommended_action": action},
        )
    )
    _event(
        db,
        conversation,
        "planner_response_recorded",
        "founder-planner",
        prior,
        {"proposal_digest": digest},
    )


def conversation_messages(
    db: Session, conversation_id: uuid.UUID
) -> list[FounderConversationMessage]:
    return list(
        db.scalars(
            select(FounderConversationMessage)
            .where(FounderConversationMessage.conversation_id == conversation_id)
            .order_by(FounderConversationMessage.sequence)
        )
    )


def latest_task(db: Session, conversation_id: uuid.UUID) -> Task | None:
    return db.scalar(
        select(Task)
        .where(Task.conversation_id == conversation_id)
        .order_by(Task.created_at.desc())
        .limit(1)
    )


def active_conversation(db: Session, founder_key: str) -> FounderConversation | None:
    return db.scalar(
        select(FounderConversation)
        .where(
            FounderConversation.founder_key == founder_key,
            FounderConversation.status.in_(OPEN_STATUSES),
        )
        .order_by(FounderConversation.updated_at.desc())
        .limit(1)
    )


def _planning_task(
    db: Session, conversation: FounderConversation, messages: list[str], actor: str
) -> Task:
    now = datetime.now(UTC)
    suggested = {
        "program_id": f"HERMES-{conversation.short_id.upper()}",
        "hypothesis_id": f"HERMES-{conversation.short_id.upper()}-H1",
    }
    contract = {
        "schema_version": 2,
        "request_kind": "task",
        "objective": messages[0],
        "conversation_id": str(conversation.id),
        "conversation_revision": conversation.revision,
        "conversation_context": messages[-20:],
        "suggested_identifiers": suggested,
        "specification_guide": _specification_guide(conversation.project),
        "grounding_context": _grounding_context(db, conversation.project, messages[-1]),
    }
    task = build_task(
        TaskCreate(
            task_number=f"FOUNDER-CONVERSATION-{now:%Y%m%dT%H%M%S%fZ}",
            project=conversation.project or "swarm-control-plane",
            task_type="founder_request",
            title=_title(messages[0]),
            objective=conversation.working_summary,
            priority=70,
            risk_level=1 if conversation.project == "bulletproof_bt" else 0,
            created_by=actor,
            input_contract=contract,
            expected_outputs=["reviewed structured execution plan"],
            acceptance_criteria=[],
            approval_policy={
                "kind": "automatic",
                "risk": 1 if conversation.project == "bulletproof_bt" else 0,
            },
            approval_required=False,
            required_capabilities=["founder-intake"],
            allowed_machines=["vm1-developer"],
            max_attempts=1,
        )
    )
    task.conversation_id = conversation.id
    task.conversation_revision = conversation.revision
    return task


def record_planning_started(db: Session, task: Task) -> None:
    if task.conversation_id is None:
        return
    conversation = db.get(FounderConversation, task.conversation_id)
    if conversation is None or conversation.revision != task.conversation_revision:
        return
    prior = conversation.status
    conversation.status = "planning"
    _event(db, conversation, "conversation_planning_started", "founder-planner", prior, {"task_id": str(task.id)})
    from app.models import FounderNotification

    db.add(
        FounderNotification(
            kind="conversation_planning",
            entity_id=conversation.id,
            deduplication_key=(
                f"conversation-planning:{conversation.id}:{conversation.revision}"
            ),
            state="pending",
            payload={
                "conversation_id": str(conversation.id),
                "short_id": conversation.short_id,
                "title": conversation.title,
                "revision": conversation.revision,
                "task_id": str(task.id),
            },
        )
    )


def _grounding_context(db: Session, project: str | None, query: str) -> dict:
    from app.models import (
        Agent,
        AlphaResearchMandate,
        ResearchDatasetManifest,
        ResearchHypothesis,
    )
    from app.schemas.retrieval import HybridRetrievalRequest
    from app.services.evidence import ORCHESTRATOR_ACCESS
    from app.services.retrieval import hybrid_search

    datasets = db.scalars(
        select(ResearchDatasetManifest).order_by(ResearchDatasetManifest.registered_at.desc()).limit(12)
    ).all()
    hypotheses = db.scalars(
        select(ResearchHypothesis).order_by(ResearchHypothesis.registered_at.desc()).limit(12)
    ).all()
    agents = db.scalars(select(Agent).where(Agent.is_enabled.is_(True)).order_by(Agent.slug).limit(50)).all()
    mandates = db.scalars(
        select(AlphaResearchMandate)
        .where(AlphaResearchMandate.status == "active", AlphaResearchMandate.valid_until > datetime.now(UTC))
        .order_by(AlphaResearchMandate.created_at.desc())
        .limit(3)
    ).all()
    try:
        retrieval = hybrid_search(
            db,
            HybridRetrievalRequest(query=query[:1000], limit=5, project=None),
            ORCHESTRATOR_ACCESS,
        )
        knowledge = {
            "available": True,
            "corpus_digest": retrieval["corpus_digest"],
            "confidence": retrieval["confidence"],
            "abstained": retrieval["abstained"],
            "hits": [
                {
                    "object_id": str(hit["object_id"]),
                    "content_digest": hit["citation"]["content_digest"],
                    "coordinates": hit["citation"]["coordinates"],
                    "text": hit["text"][:1200],
                    "confidence": hit["confidence"],
                }
                for hit in retrieval["hits"]
            ],
        }
    except HTTPException as exc:
        knowledge = {"available": False, "reason": str(exc.detail)}
    return {
        "project": project,
        "knowledge": knowledge,
        "datasets": [
            {
                "id": str(item.id),
                "key": item.manifest_key,
                "digest": item.manifest_digest,
                "summary": {
                    key: item.manifest[key]
                    for key in (
                        "schema_version", "dataset_id", "venue", "instrument",
                        "timeframe", "start", "end", "availability",
                    )
                    if key in item.manifest
                },
            }
            for item in datasets
        ],
        "hypotheses": [
            {
                "id": str(item.id),
                "key": item.hypothesis_key,
                "digest": item.record_digest,
                "summary": {
                    key: item.specification[key]
                    for key in ("research_question", "hypothesis", "dataset", "status")
                    if key in item.specification
                },
            }
            for item in hypotheses
        ],
        "task_capabilities": [
            {"slug": item.slug, "machine": item.machine, "capabilities": item.capabilities, "risk_ceiling": item.risk_ceiling}
            for item in agents
        ],
        "active_research_mandates": [
            {
                "id": str(item.id),
                "key": item.mandate_key,
                "digest": item.mandate_digest,
                "valid_until": item.valid_until.isoformat(),
                "allowed_venues": item.specification.get("allowed_venues", []),
                "allowed_instruments": item.specification.get("allowed_instruments", []),
                "execution_window_start": item.specification.get("execution_window_start"),
                "execution_window_end": item.specification.get("execution_window_end"),
                "maximum_variants": min(8, int(item.budget.get("maximum_variants_per_hypothesis", 8))),
            }
            for item in mandates
        ],
        "founder_hypothesis_intake_policy": {
            "minimum_history_days": 365,
            "maximum_variants": 8,
            "universe_selection_policy": "preregistered_point_in_time",
            "universe_slices": ["stable", "volatile"],
            "selection_rule": "freeze the selected universe and alternatives before outcome evaluation",
            "workflow": "founder-hypothesis-intake",
        },
        "claim_boundary": "Context is advisory evidence only and grants no execution authority.",
    }


def _specification_guide(project: str | None) -> dict:
    if project == "bulletproof_bt":
        return {
            "required": [
                "repository",
                "workflow",
                "base_ref",
                "hypothesis",
                "dataset",
                "seed",
                "observations",
                "train_fraction",
                "transaction_cost_bps",
                "acceptance",
            ],
            "system_generated": ["program_id", "hypothesis_id", "task_number"],
            "formats": {
                "base_ref": "Git ref such as main",
                "train_fraction": "decimal 0.50-0.80",
                "transaction_cost_bps": "number 0-100",
                "acceptance": "Sharpe, drawdown, trade-count and cost-stress thresholds",
            },
            "reasonable_defaults": {
                "base_ref": "main",
                "seed": 20260730,
                "observations": 1200,
                "train_fraction": 0.65,
                "transaction_cost_bps": 5.0,
                "acceptance": {
                    "minimum_out_of_sample_sharpe": 1.0,
                    "maximum_out_of_sample_drawdown": 0.25,
                    "minimum_out_of_sample_trades": 50,
                    "minimum_cost_stress_sharpe": 0.5,
                },
            },
            "never_default": [
                "hypothesis meaning",
                "unavailable dataset",
                "live trading",
                "production promotion",
            ],
            "founder_hypothesis_intake": {
                "purpose": "queue a founder idea for RI evidence retrieval and independent senior-researcher challenge before any test",
                "minimum_history_days": 365,
                "maximum_variants": 8,
                "universe_selection_policy": "preregistered_point_in_time",
            },
        }
    return {
        "required": ["bounded objective", "target route", "acceptance criteria"],
        "system_generated": ["task_number"],
        "reasonable_defaults": {},
        "never_default": ["credentials", "destructive action", "permission expansion"],
    }


def _classify_project(messages: list[str]) -> str:
    text = " ".join(messages).lower()
    if any(word in text for word in INFRA_WORDS):
        return "swarm-control-plane"
    if any(word in text for word in RESEARCH_WORDS):
        return "bulletproof_bt"
    if any(word in text for word in KNOWLEDGE_WORDS):
        return "knowledge"
    return "swarm-control-plane"


def _founder_messages(db: Session, conversation_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(FounderConversationMessage.content)
            .where(
                FounderConversationMessage.conversation_id == conversation_id,
                FounderConversationMessage.role == "founder",
            )
            .order_by(FounderConversationMessage.sequence)
        )
    )


def _bounded_summary(messages: list[str]) -> str:
    return "\n\n".join(messages)[-12000:]


def _title(value: str) -> str:
    return " ".join(re.sub(r"\s+", " ", value).split()[:12])[:160]


def _event(
    db: Session,
    conversation: FounderConversation,
    event_type: str,
    actor: str,
    prior: str | None,
    payload: dict,
) -> None:
    db.add(
        FounderConversationEvent(
            conversation_id=conversation.id,
            event_type=event_type,
            actor=actor,
            prior_status=prior,
            resulting_status=conversation.status,
            revision=conversation.revision,
            payload=payload,
        )
    )
