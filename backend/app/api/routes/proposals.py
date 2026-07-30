from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent, FounderProposal
from app.schemas import (
    FounderProposalCreate,
    FounderProposalDecision,
    FounderProposalResponse,
    TaskResponse,
)
from app.services.proposals import (
    create_proposal,
    materialize_proposal,
    reject_proposal,
)
from app.services.tasks import (
    append_task_event,
    lock_task,
    serialize_task,
    verify_task_lease,
)

router = APIRouter(prefix="/v1/proposals", tags=["founder-proposals"])
agent_router = APIRouter(prefix="/v1/agent/tasks", tags=["agent-task-runtime"])


@agent_router.post(
    "/{task_id}/proposal",
    response_model=FounderProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_proposal(
    task_id: uuid.UUID,
    payload: FounderProposalCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> FounderProposalResponse:
    task = lock_task(db, task_id)
    verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"running"},
    )
    proposal = create_proposal(
        db, source_task=task, planner=agent, document=payload.proposal
    )
    append_task_event(
        db,
        task,
        "founder_proposal_created",
        "Planner submitted a structured founder proposal.",
        agent_id=agent.id,
        payload={
            "proposal_id": str(proposal.id),
            "proposal_digest": proposal.proposal_digest,
            "recommended_action": payload.proposal.recommended_action,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A proposal already exists for this founder request.",
        ) from exc
    db.refresh(proposal)
    return FounderProposalResponse.model_validate(proposal)


@router.get(
    "",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[FounderProposalResponse],
)
def list_proposals(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderProposalResponse]:
    proposals = db.scalars(
        select(FounderProposal).order_by(FounderProposal.created_at.desc())
    ).all()
    return [FounderProposalResponse.model_validate(item) for item in proposals]


@router.post(
    "/{proposal_id}/materialize",
    dependencies=[Depends(require_orchestrator)],
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_and_materialize(
    proposal_id: uuid.UUID,
    payload: FounderProposalDecision,
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    proposal = _lock_proposal(db, proposal_id)
    try:
        task = materialize_proposal(
            db, proposal, actor=payload.actor, reason=payload.reason
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Proposal materialization conflicted."
        ) from exc
    db.refresh(task)
    return TaskResponse.model_validate(serialize_task(task))


@router.post(
    "/{proposal_id}/reject",
    dependencies=[Depends(require_orchestrator)],
    response_model=FounderProposalResponse,
)
def reject(
    proposal_id: uuid.UUID,
    payload: FounderProposalDecision,
    db: Annotated[Session, Depends(get_db)],
) -> FounderProposalResponse:
    proposal = _lock_proposal(db, proposal_id)
    reject_proposal(proposal, actor=payload.actor, reason=payload.reason)
    db.commit()
    db.refresh(proposal)
    return FounderProposalResponse.model_validate(proposal)


def _lock_proposal(db: Session, proposal_id: uuid.UUID) -> FounderProposal:
    proposal = db.scalar(
        select(FounderProposal)
        .where(FounderProposal.id == proposal_id)
        .with_for_update()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposal
