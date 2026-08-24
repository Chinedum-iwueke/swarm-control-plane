from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_founder_channel, require_orchestrator
from app.db.session import get_db
from app.models import (
    Artifact,
    FounderConversation,
    FounderConversationEvent,
    FounderProposal,
    Task,
    TaskApproval,
    TaskEvent,
)
from app.schemas import (
    ApprovalResponse,
    ArtifactResponse,
    ConversationCreate,
    ConversationEventResponse,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationTransition,
    ConversationTurnCreate,
    ConversationTurnResponse,
    ConversationWorkspaceResponse,
    FounderProposalResponse,
    TaskDetailResponse,
    TaskEventResponse,
    TaskResponse,
)
from app.services.conversations import (
    active_conversation,
    append_turn,
    conversation_messages,
    create_conversation,
    latest_task,
    transition_conversation,
)
from app.services.tasks import serialize_task

router = APIRouter(
    prefix="/v1/conversations",
    tags=["founder-conversations"],
    dependencies=[Depends(require_orchestrator)],
)
channel_router = APIRouter(
    prefix="/v1/founder-channel/conversations",
    tags=["founder-channel"],
    dependencies=[Depends(require_founder_channel)],
)


def _response(db: Session, item: FounderConversation) -> ConversationResponse:
    task = latest_task(db, item.id)
    return ConversationResponse(
        **{
            key: getattr(item, key)
            for key in (
                "id",
                "short_id",
                "founder_key",
                "title",
                "project",
                "status",
                "working_summary",
                "current_specification",
                "specification_digest",
                "revision",
                "created_at",
                "updated_at",
                "closed_at",
            )
        },
        messages=[
            ConversationMessageResponse.model_validate(value)
            for value in conversation_messages(db, item.id)
        ],
        latest_task_id=task.id if task else None,
        latest_task_number=task.task_number if task else None,
    )


def _get(
    db: Session, conversation_id: uuid.UUID, founder_key: str | None = None
) -> FounderConversation:
    item = db.scalar(
        select(FounderConversation)
        .where(FounderConversation.id == conversation_id)
        .with_for_update()
    )
    if item is None or (founder_key is not None and item.founder_key != founder_key):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return item


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    founder_key: Annotated[str | None, Query(max_length=160)] = None,
) -> list[ConversationResponse]:
    statement = select(FounderConversation)
    if founder_key:
        statement = statement.where(FounderConversation.founder_key == founder_key)
    items = db.scalars(
        statement.order_by(FounderConversation.updated_at.desc()).limit(100)
    ).all()
    return [_response(db, item) for item in items]


@router.get("/{conversation_id}/workspace", response_model=ConversationWorkspaceResponse)
def conversation_workspace(
    conversation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationWorkspaceResponse:
    item = _get(db, conversation_id)
    events = db.scalars(
        select(FounderConversationEvent)
        .where(FounderConversationEvent.conversation_id == item.id)
        .order_by(FounderConversationEvent.id.asc())
    ).all()
    proposals = db.scalars(
        select(FounderProposal)
        .where(FounderProposal.conversation_id == item.id)
        .order_by(FounderProposal.created_at.asc())
    ).all()
    tasks = db.scalars(
        select(Task)
        .where(Task.conversation_id == item.id)
        .order_by(Task.created_at.asc())
    ).all()
    task_ids = [task.id for task in tasks]
    task_events = (
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id.in_(task_ids))
            .order_by(TaskEvent.id.asc())
        ).all()
        if task_ids
        else []
    )
    events_by_task: dict[uuid.UUID, list[TaskEvent]] = {}
    for event in task_events:
        events_by_task.setdefault(event.task_id, []).append(event)
    approvals = (
        db.scalars(
            select(TaskApproval)
            .where(TaskApproval.task_id.in_(task_ids))
            .order_by(TaskApproval.created_at.asc())
        ).all()
        if task_ids
        else []
    )
    artifacts = (
        db.scalars(
            select(Artifact)
            .where(Artifact.task_id.in_(task_ids))
            .order_by(Artifact.created_at.asc())
        ).all()
        if task_ids
        else []
    )
    return ConversationWorkspaceResponse(
        conversation=_response(db, item),
        events=[ConversationEventResponse.model_validate(value) for value in events],
        proposals=[FounderProposalResponse.model_validate(value) for value in proposals],
        tasks=[
            TaskDetailResponse(
                task=TaskResponse.model_validate(serialize_task(task)),
                events=[
                    TaskEventResponse.model_validate(event)
                    for event in events_by_task.get(task.id, [])
                ],
            )
            for task in tasks
        ],
        approvals=[ApprovalResponse.model_validate(value) for value in approvals],
        artifacts=[ArtifactResponse.model_validate(value) for value in artifacts],
    )


@router.post("", response_model=ConversationTurnResponse, status_code=201)
def new_conversation(
    payload: ConversationCreate, db: Annotated[Session, Depends(get_db)]
) -> ConversationTurnResponse:
    item, task = create_conversation(db, payload)
    db.commit()
    db.refresh(item)
    return ConversationTurnResponse(
        conversation=_response(db, item), task_id=task.id, task_number=task.task_number
    )


@router.post(
    "/{conversation_id}/turns", response_model=ConversationTurnResponse, status_code=201
)
def add_turn(
    conversation_id: uuid.UUID,
    payload: ConversationTurnCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationTurnResponse:
    item = _get(db, conversation_id, payload.founder_key)
    task = append_turn(db, item, payload)
    db.commit()
    db.refresh(item)
    return ConversationTurnResponse(
        conversation=_response(db, item), task_id=task.id, task_number=task.task_number
    )


@router.post("/{conversation_id}/transitions", response_model=ConversationResponse)
def transition(
    conversation_id: uuid.UUID,
    payload: ConversationTransition,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse:
    item = _get(db, conversation_id, payload.founder_key)
    transition_conversation(
        db,
        item,
        action=payload.action,
        actor=payload.founder_key,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(item)
    return _response(db, item)


@channel_router.get("/active", response_model=ConversationResponse | None)
def channel_active(
    founder_key: Annotated[str, Query(max_length=160)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse | None:
    item = active_conversation(db, founder_key)
    return _response(db, item) if item else None


@channel_router.get("", response_model=list[ConversationResponse])
def channel_list(
    founder_key: Annotated[str, Query(max_length=160)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConversationResponse]:
    items = db.scalars(
        select(FounderConversation)
        .where(FounderConversation.founder_key == founder_key)
        .order_by(FounderConversation.updated_at.desc())
        .limit(20)
    ).all()
    return [_response(db, item) for item in items]


@channel_router.post("", response_model=ConversationTurnResponse, status_code=201)
def channel_new(
    payload: ConversationCreate, db: Annotated[Session, Depends(get_db)]
) -> ConversationTurnResponse:
    return new_conversation(payload, db)


@channel_router.post(
    "/{conversation_id}/turns", response_model=ConversationTurnResponse, status_code=201
)
def channel_turn(
    conversation_id: uuid.UUID,
    payload: ConversationTurnCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationTurnResponse:
    return add_turn(conversation_id, payload, db)


@channel_router.post(
    "/{conversation_id}/transitions", response_model=ConversationResponse
)
def channel_transition(
    conversation_id: uuid.UUID,
    payload: ConversationTransition,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationResponse:
    return transition(conversation_id, payload, db)
