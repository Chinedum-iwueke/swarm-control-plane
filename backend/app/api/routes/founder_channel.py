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
from app.models import (
    EngineeringMission,
    FounderProposal,
    Task,
    TaskApproval,
    TaskDependency,
)
from app.schemas import (
    ApprovalResponse,
    FounderChannelApproval,
    FounderChannelDecision,
    FounderChannelMission,
    FounderChannelRequest,
    FounderProposalResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.governance import approve_task, decide_task
from app.services.proposals import materialize_proposal, reject_proposal
from app.services.supervision import approve_supervision
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
        raise HTTPException(
            status_code=409, detail="Request creation conflicted."
        ) from exc
    db.refresh(task)
    return TaskResponse.model_validate(serialize_task(task))


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TaskResponse]:
    tasks = db.scalars(select(Task).order_by(Task.updated_at.desc()).limit(limit)).all()
    return [TaskResponse.model_validate(serialize_task(task)) for task in tasks]


@router.get("/proposals", response_model=list[FounderProposalResponse])
def list_proposals(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderProposalResponse]:
    values = db.scalars(
        select(FounderProposal).order_by(FounderProposal.created_at.desc())
    ).all()
    return [FounderProposalResponse.model_validate(item) for item in values]


@router.get("/missions", response_model=list[FounderChannelMission])
def list_supervised_missions(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderChannelMission]:
    missions = db.scalars(
        select(EngineeringMission)
        .where(EngineeringMission.supervision_enabled.is_(True))
        .order_by(EngineeringMission.updated_at.desc())
    ).all()
    return [
        FounderChannelMission(
            id=item.id,
            milestone_id=item.milestone_id,
            objective=item.objective,
            status=item.status,
            manifest_digest=item.manifest_digest,
            supervision_status=item.supervision_status or "unknown",
            supervision_policy=item.supervision_policy,
            supervision_exception=item.supervision_exception,
            deadline_at=item.deadline_at,
            actionable=item.supervision_status == "pending_approval",
        )
        for item in missions
    ]


@router.post("/missions/{mission_id}/approve", response_model=FounderChannelMission)
def approve_supervised_mission(
    mission_id: uuid.UUID,
    payload: FounderChannelDecision,
    db: Annotated[Session, Depends(get_db)],
) -> FounderChannelMission:
    mission = db.scalar(
        select(EngineeringMission)
        .where(EngineeringMission.id == mission_id)
        .with_for_update()
    )
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found.")
    approve_supervision(db, mission, actor="founder-telegram", reason=payload.reason)
    db.commit()
    db.refresh(mission)
    return FounderChannelMission(
        id=mission.id,
        milestone_id=mission.milestone_id,
        objective=mission.objective,
        status=mission.status,
        manifest_digest=mission.manifest_digest,
        supervision_status=mission.supervision_status or "unknown",
        supervision_policy=mission.supervision_policy,
        supervision_exception=mission.supervision_exception,
        deadline_at=mission.deadline_at,
        actionable=False,
    )


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


@router.get("/approvals", response_model=list[FounderChannelApproval])
def list_approvals(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderChannelApproval]:
    values = db.scalars(
        select(TaskApproval).order_by(TaskApproval.created_at.desc())
    ).all()
    return [_founder_approval(db, item) for item in values]


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
        select(TaskApproval).where(TaskApproval.id == approval_id).with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if action == "approve":
        view = _founder_approval(db, approval)
        if not view.actionable:
            raise HTTPException(
                status_code=409,
                detail="Approval is blocked by task dependencies or mission state.",
            )
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


def _founder_approval(db: Session, approval: TaskApproval) -> FounderChannelApproval:
    task = db.get(Task, approval.task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="Approval task is unavailable.")
    dependencies = db.execute(
        select(Task.task_number, Task.status)
        .join(
            TaskDependency,
            Task.id == TaskDependency.depends_on_task_id,
        )
        .where(TaskDependency.task_id == task.id)
    ).all()
    blocked_by = [
        f"{task_number}:{task_status}"
        for task_number, task_status in dependencies
        if task_status != "succeeded"
    ]
    mission = (
        db.get(EngineeringMission, task.mission_id)
        if task.mission_id is not None
        else None
    )
    now = datetime.now(UTC)
    mission_ready = mission is None or (
        mission.status == "active" and mission.deadline_at > now
    )
    actionable = (
        approval.status == "pending"
        and task.status == "pending_approval"
        and not blocked_by
        and mission_ready
    )
    base = ApprovalResponse.model_validate(approval).model_dump(mode="python")
    contract = task.input_contract if isinstance(task.input_contract, dict) else {}
    return FounderChannelApproval(
        **base,
        task_number=task.task_number,
        task_title=task.title,
        operation=contract.get("operation"),
        milestone_step_id=task.milestone_step_id,
        mission_id=task.mission_id,
        task_status=task.status,
        actionable=actionable,
        blocked_by=blocked_by,
        mission_deadline_at=mission.deadline_at if mission is not None else None,
    )
