from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent, ApprovalEvent, Artifact, TaskApproval
from app.schemas import (
    ApprovalCenterDecision,
    ApprovalCenterDecisionReceipt,
    ApprovalCenterItem,
    ApprovalCenterResponse,
    ApprovalDecision,
    ApprovalEventResponse,
    ApprovalResponse,
    ArtifactCreate,
    ArtifactResponse,
)
from app.services.approval_center import approval_center, approval_center_item
from app.services.authority import canonical_digest, resolve_task_approval
from app.services.governance import append_approval_event, approve_task, decide_task
from app.services.tasks import lock_task, verify_task_lease

router = APIRouter(tags=["governance"])


@router.get(
    "/v1/approval-center",
    dependencies=[Depends(require_orchestrator)],
    response_model=ApprovalCenterResponse,
)
def approval_center_overview(
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalCenterResponse:
    return ApprovalCenterResponse.model_validate(approval_center(db))


@router.get(
    "/v1/approval-center/{approval_id}",
    dependencies=[Depends(require_orchestrator)],
    response_model=ApprovalCenterItem,
)
def approval_center_review(
    approval_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalCenterItem:
    return ApprovalCenterItem.model_validate(
        approval_center_item(db, _approval(db, approval_id))
    )


@router.post(
    "/v1/approval-center/{approval_id}/{action}",
    dependencies=[Depends(require_orchestrator)],
    response_model=ApprovalCenterDecisionReceipt,
)
def approval_center_decision(
    approval_id: UUID,
    action: str,
    payload: ApprovalCenterDecision,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalCenterDecisionReceipt:
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=404, detail="Unknown approval action.")
    approval = db.scalar(
        select(TaskApproval).where(TaskApproval.id == approval_id).with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    review = approval_center_item(db, approval)
    if review["review_digest"] != payload.expected_review_digest:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "approval-review-superseded",
                "current_review_digest": review["review_digest"],
            },
        )
    if action == "approve" and not review["actionable"]:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "approval-not-actionable",
                "blocked_by": review["blocked_by"],
            },
        )
    resolve_task_approval(
        db,
        approval,
        actor=payload.actor,
        action=action,
        exception_id=payload.authority_exception_id,
    )
    if action == "approve":
        approve_task(
            db,
            approval,
            actor=payload.actor,
            reason=payload.reason,
            expires_in_seconds=payload.expires_in_seconds,
        )
    else:
        decide_task(
            db,
            approval,
            actor=payload.actor,
            reason=payload.reason,
            action="reject",
        )
    receipt_document = {
        "schema_version": "digest-safe-approval-decision-v1.0.0",
        "approval_id": str(approval.id),
        "task_id": str(approval.task_id),
        "action": action,
        "actor": payload.actor,
        "review_digest": payload.expected_review_digest,
        "plan_digest": approval.plan_digest,
        "decision_reason_digest": canonical_digest(payload.reason),
        "expires_in_seconds": payload.expires_in_seconds
        if action == "approve"
        else None,
    }
    receipt_digest = canonical_digest(receipt_document)
    event = append_approval_event(
        db,
        approval,
        "approval_center_decision_receipt",
        payload.actor,
        "Digest-safe approval-center decision retained.",
        {**receipt_document, "receipt_digest": receipt_digest},
    )
    db.commit()
    db.refresh(approval)
    return ApprovalCenterDecisionReceipt(
        approval=ApprovalResponse.model_validate(approval),
        action=action,
        review_digest=payload.expected_review_digest,
        receipt_digest=receipt_digest,
        event_id=event.id,
    )


@router.get(
    "/v1/approvals",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[ApprovalResponse],
)
def list_approvals(
    db: Annotated[Session, Depends(get_db)],
    approval_status: Annotated[str | None, Query(alias="status")] = None,
) -> list[ApprovalResponse]:
    query = select(TaskApproval)
    if approval_status:
        query = query.where(TaskApproval.status == approval_status)
    approvals = db.scalars(query.order_by(TaskApproval.created_at.desc())).all()
    return [ApprovalResponse.model_validate(item) for item in approvals]


@router.get(
    "/v1/approvals/{approval_id}/events",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[ApprovalEventResponse],
)
def list_approval_events(
    approval_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[ApprovalEventResponse]:
    events = db.scalars(
        select(ApprovalEvent)
        .where(ApprovalEvent.approval_id == approval_id)
        .order_by(ApprovalEvent.id)
    ).all()
    return [ApprovalEventResponse.model_validate(item) for item in events]


@router.post(
    "/v1/approvals/{approval_id}/approve",
    dependencies=[Depends(require_orchestrator)],
    response_model=ApprovalResponse,
)
def grant_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalResponse:
    approval = _approval(db, approval_id)
    resolve_task_approval(
        db,
        approval,
        actor=payload.actor,
        action="approve",
        exception_id=payload.authority_exception_id,
    )
    approve_task(
        db,
        approval,
        actor=payload.actor,
        reason=payload.reason,
        expires_in_seconds=payload.expires_in_seconds,
    )
    db.commit()
    db.refresh(approval)
    return ApprovalResponse.model_validate(approval)


@router.post(
    "/v1/approvals/{approval_id}/{action}",
    dependencies=[Depends(require_orchestrator)],
    response_model=ApprovalResponse,
)
def reject_or_revoke_approval(
    approval_id: UUID,
    action: str,
    payload: ApprovalDecision,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalResponse:
    if action not in {"reject", "revoke"}:
        raise HTTPException(status_code=404, detail="Unknown approval action.")
    approval = _approval(db, approval_id)
    resolve_task_approval(
        db,
        approval,
        actor=payload.actor,
        action=action,
        exception_id=payload.authority_exception_id,
    )
    decide_task(
        db, approval, actor=payload.actor, reason=payload.reason, action=action
    )
    db.commit()
    db.refresh(approval)
    return ApprovalResponse.model_validate(approval)


@router.get(
    "/v1/artifacts",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[ArtifactResponse],
)
def list_artifacts(
    db: Annotated[Session, Depends(get_db)],
    task_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ArtifactResponse]:
    query = select(Artifact)
    if task_id:
        query = query.where(Artifact.task_id == task_id)
    artifacts = db.scalars(query.order_by(Artifact.created_at.desc()).limit(limit)).all()
    return [ArtifactResponse.model_validate(item) for item in artifacts]


@router.post(
    "/v1/agent/tasks/{task_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_artifact(
    task_id: UUID,
    payload: ArtifactCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> ArtifactResponse:
    task = lock_task(db, task_id)
    verify_task_lease(
        task, agent, payload.lease_token, allowed_statuses={"leased", "running"}
    )
    if not payload.location.startswith(f"{payload.storage_backend}://"):
        raise HTTPException(status_code=422, detail="Storage backend mismatch.")
    artifact = Artifact(
        task_id=task.id,
        agent_id=agent.id,
        attempt_number=task.attempt_count,
        artifact_type=payload.artifact_type,
        name=payload.name,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        location=payload.location,
        storage_backend=payload.storage_backend,
        workflow=payload.workflow,
        workflow_version=payload.workflow_version,
        source_commit=payload.source_commit,
        confidentiality=payload.confidentiality,
        retention_class=payload.retention_class,
        verification_status="worker-digest",
        expires_at=payload.expires_at,
        metadata_json=payload.metadata,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return ArtifactResponse.model_validate(artifact)


def _approval(db: Session, approval_id: UUID) -> TaskApproval:
    approval = db.get(TaskApproval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    return approval
