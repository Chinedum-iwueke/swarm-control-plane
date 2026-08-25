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
    FounderNotification,
    FounderProposal,
    OperationalNote,
    ResearchDailyCycle,
    Task,
    TaskApproval,
)
from app.schemas import (
    ApprovalResponse,
    FounderChannelApproval,
    FounderChannelDecision,
    FounderChannelMission,
    FounderChannelRequest,
    FounderNotificationAcknowledgement,
    FounderNotificationResponse,
    FounderProposalResponse,
    TaskCreate,
    TaskResponse,
)
from app.schemas.operational_note import OperationalNoteResponse
from app.schemas.research_program import ResearchDailyCycleResponse
from app.services.authority import resolve_task_approval
from app.services.founder_notifications import (
    acknowledge_notification,
    approval_readiness,
    reconcile_founder_notifications,
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
    task = build_task(_founder_request_task(payload, now))
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


def _founder_request_task(
    payload: FounderChannelRequest,
    now: datetime,
) -> TaskCreate:
    # Intake only produces a reviewable proposal. The proposal carries the risk
    # and approval policy for any eventual execution task.
    return TaskCreate(
        task_number=f"FOUNDER-TELEGRAM-{now:%Y%m%dT%H%M%S%fZ}",
        project=payload.project,
        task_type="founder_request",
        title=payload.title,
        objective=payload.objective,
        priority=70,
        risk_level=0,
        created_by="founder-telegram",
        input_contract={
            "schema_version": 1,
            "request_kind": payload.kind,
            "objective": payload.objective,
        },
        expected_outputs=["reviewed structured execution plan"],
        acceptance_criteria=payload.acceptance_criteria,
        approval_policy={"kind": "automatic", "risk": 0},
        approval_required=False,
        required_capabilities=["founder-intake"],
        allowed_machines=["vm1-developer"],
        max_attempts=1,
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TaskResponse]:
    tasks = db.scalars(select(Task).order_by(Task.updated_at.desc()).limit(limit)).all()
    return [TaskResponse.model_validate(serialize_task(task)) for task in tasks]


@router.get("/operational-notes", response_model=list[OperationalNoteResponse])
def list_operational_notes(
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[OperationalNoteResponse]:
    statement = select(OperationalNote)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            OperationalNote.subject.ilike(pattern)
            | OperationalNote.finding.ilike(pattern)
            | OperationalNote.note_key.ilike(pattern)
        )
    notes = db.scalars(
        statement.order_by(OperationalNote.updated_at.desc()).limit(limit)
    ).all()
    return [OperationalNoteResponse.model_validate(item) for item in notes]


@router.get("/research-cycles", response_model=list[ResearchDailyCycleResponse])
def list_research_cycles(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=30)] = 7,
) -> list[ResearchDailyCycleResponse]:
    cycles = db.scalars(
        select(ResearchDailyCycle)
        .order_by(ResearchDailyCycle.created_at.desc())
        .limit(limit)
    ).all()
    return [ResearchDailyCycleResponse.model_validate(item) for item in cycles]


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


@router.get("/notifications", response_model=list[FounderNotificationResponse])
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
) -> list[FounderNotificationResponse]:
    values = reconcile_founder_notifications(db)
    db.commit()
    return [FounderNotificationResponse.model_validate(item) for item in values]


@router.post(
    "/notifications/{notification_id}/acknowledge",
    response_model=FounderNotificationResponse,
)
def acknowledge_founder_notification(
    notification_id: uuid.UUID,
    payload: FounderNotificationAcknowledgement,
    db: Annotated[Session, Depends(get_db)],
) -> FounderNotificationResponse:
    notification = db.scalar(
        select(FounderNotification)
        .where(FounderNotification.id == notification_id)
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    acknowledge_notification(notification, payload.delivery_reference)
    db.commit()
    db.refresh(notification)
    return FounderNotificationResponse.model_validate(notification)


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
        resolve_task_approval(
            db,
            approval,
            actor="founder-telegram",
            action="approve",
            exception_id=payload.authority_exception_id,
        )
        approve_task(
            db,
            approval,
            actor="founder-telegram",
            reason=payload.reason,
            expires_in_seconds=payload.expires_in_seconds,
        )
    elif action == "reject":
        resolve_task_approval(
            db,
            approval,
            actor="founder-telegram",
            action="reject",
            exception_id=payload.authority_exception_id,
        )
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
    actionable, blocked_by, task, mission = approval_readiness(db, approval)
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
