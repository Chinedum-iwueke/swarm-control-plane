from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_founder_channel
from app.db.session import get_db
from app.models import FounderProposal, Task, TaskApproval
from app.schemas import (
    ApprovalResponse,
    FounderChannelDecision,
    FounderChannelRequest,
    FounderProposalResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.governance import approve_task, decide_task
from app.services.proposals import materialize_proposal, reject_proposal
from app.services.tasks import build_task, persist_new_task, serialize_task

router = APIRouter(
    prefix="/v1/founder-channel",
    tags=["founder-channel"],
    dependencies=[Depends(require_founder_channel)],
)


@router.post(
    "/requests",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    payload: FounderChannelRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    now = datetime.now(UTC)
    task = build_task(
        TaskCreate(
            task_number=f"FOUNDER-TELEGRAM-{now:%Y%m%dT%H%M%S%fZ}",
            project=payload.project,
            task_type="founder_request",
            title=payload.title,
            objective=payload.objective,
            priority=70,
            risk_level=payload.risk_level,
            created_by="founder-telegram",
            input_contract={
                "schema_version": 1,
                "request_kind": payload.kind,
                "objective": payload.objective,
            },
            expected_outputs=["reviewed structured execution plan"],
            acceptance_criteria=payload.acceptance_criteria,
            approval_policy={
                "kind": "explicit" if payload.risk_level >= 2 else "automatic",
                "risk": payload.risk_level,
            },
            approval_required=payload.risk_level >= 2,
            required_capabilities=["founder-intake"],
            allowed_machines=["vm1-developer"],
            max_attempts=1,
        )
    )
    try:
        persist_new_task(db, task)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Request creation conflicted.") from exc
    db.refresh(task)
    return TaskResponse.model_validate(serialize_task(task))


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TaskResponse]:
    tasks = db.scalars(
        select(Task).order_by(Task.updated_at.desc()).limit(limit)
    ).all()
    return [TaskResponse.model_validate(serialize_task(task)) for task in tasks]


@router.get("/proposals", response_model=list[FounderProposalResponse])
def list_proposals(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderProposalResponse]:
    values = db.scalars(
        select(FounderProposal).order_by(FounderProposal.created_at.desc())
    ).all()
    return [FounderProposalResponse.model_validate(item) for item in values]


@router.post(
    "/proposals/{proposal_id}/{action}",
    response_model=TaskResponse | FounderProposalResponse,
)
def decide_proposal(
    proposal_id: uuid.UUID,
    action: str,
    payload: FounderChannelDecision,
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse | FounderProposalResponse:
    proposal = db.scalar(
        select(FounderProposal)
        .where(FounderProposal.id == proposal_id)
        .with_for_update()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    if action == "materialize":
        task = materialize_proposal(
            db,
            proposal,
            actor="founder-telegram",
            reason=payload.reason,
        )
        db.commit()
        db.refresh(task)
        return TaskResponse.model_validate(serialize_task(task))
    if action == "reject":
        reject_proposal(
            proposal,
            actor="founder-telegram",
            reason=payload.reason,
        )
        db.commit()
        db.refresh(proposal)
        return FounderProposalResponse.model_validate(proposal)
    raise HTTPException(status_code=404, detail="Unknown proposal action.")


@router.get("/approvals", response_model=list[ApprovalResponse])
def list_approvals(
    db: Annotated[Session, Depends(get_db)],
) -> list[ApprovalResponse]:
    values = db.scalars(
        select(TaskApproval).order_by(TaskApproval.created_at.desc())
    ).all()
    return [ApprovalResponse.model_validate(item) for item in values]


@router.post(
    "/approvals/{approval_id}/{action}",
    response_model=ApprovalResponse,
)
def decide_approval(
    approval_id: uuid.UUID,
    action: str,
    payload: FounderChannelDecision,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalResponse:
    approval = db.scalar(
        select(TaskApproval)
        .where(TaskApproval.id == approval_id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if action == "approve":
        approve_task(
            db,
            approval,
            actor="founder-telegram",
            reason=payload.reason,
            expires_in_seconds=payload.expires_in_seconds,
        )
    elif action == "reject":
        decide_task(
            db,
            approval,
            actor="founder-telegram",
            reason=payload.reason,
            action="reject",
        )
    else:
        raise HTTPException(status_code=404, detail="Unknown approval action.")
    db.commit()
    db.refresh(approval)
    return ApprovalResponse.model_validate(approval)
