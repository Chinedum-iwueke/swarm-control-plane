from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, FounderConversation, FounderProposal, Task
from app.schemas import FounderProposalDocument, ProposedTask, TaskCreate
from app.services.tasks import append_task_event, build_task, persist_new_task


def proposal_digest(document: FounderProposalDocument) -> str:
    encoded = json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_proposal(
    db: Session,
    *,
    source_task: Task,
    planner: Agent,
    document: FounderProposalDocument,
) -> FounderProposal:
    if source_task.task_type != "founder_request":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Proposals may only be submitted for founder_request tasks.",
        )
    if "founder-intake" not in planner.capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is not authorized to plan founder requests.",
        )
    if source_task.conversation_id is not None:
        conversation = db.scalar(
            select(FounderConversation)
            .where(FounderConversation.id == source_task.conversation_id)
            .with_for_update()
        )
        if (
            conversation is None
            or source_task.conversation_revision != conversation.revision
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A newer founder turn superseded this planning revision.",
            )
    existing = db.scalar(
        select(FounderProposal).where(FounderProposal.source_task_id == source_task.id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A proposal already exists for this founder request.",
        )
    proposal = FounderProposal(
        source_task_id=source_task.id,
        conversation_id=source_task.conversation_id,
        conversation_revision=source_task.conversation_revision,
        planner_agent_id=planner.id,
        status="proposed",
        proposal=document.model_dump(mode="json"),
        proposal_digest=proposal_digest(document),
    )
    db.add(proposal)
    db.flush()
    from app.services.conversations import record_planner_response

    record_planner_response(
        db,
        source_task,
        proposal.proposal,
        proposal.proposal_digest,
    )
    return proposal


def materialize_proposal(
    db: Session,
    proposal: FounderProposal,
    *,
    actor: str,
    reason: str,
    now: datetime | None = None,
) -> Task:
    if proposal.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal is already {proposal.status}.",
        )
    document = FounderProposalDocument.model_validate(proposal.proposal)
    if document.recommended_action != "create_task" or document.proposed_task is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This proposal does not recommend task creation.",
        )
    if proposal.conversation_id is not None:
        conversation = db.scalar(
            select(FounderConversation)
            .where(FounderConversation.id == proposal.conversation_id)
            .with_for_update()
        )
        if (
            conversation is None
            or proposal.conversation_revision != conversation.revision
            or conversation.specification_digest != proposal.proposal_digest
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A newer conversation revision superseded this proposal.",
            )
    source = db.get(Task, proposal.source_task_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source request not found.")
    created_at = now or datetime.now(UTC)
    payload = _task_create(document.proposed_task, source, actor, created_at)
    task = build_task(payload)
    task.conversation_id = source.conversation_id
    task.conversation_revision = source.conversation_revision
    persist_new_task(db, task)
    if document.proposed_task.task_type == "founder_hypothesis_intake":
        from app.models.alpha_discovery import AlphaResearchMandate
        from app.schemas.alpha_discovery import AlphaFounderResearchIdeaCreate
        from app.services.alpha_discovery import queue_founder_idea

        contract = document.proposed_task.input_contract
        mandate = db.scalar(
            select(AlphaResearchMandate)
            .where(AlphaResearchMandate.id == contract.mandate_id)
            .with_for_update()
        )
        if mandate is None:
            raise HTTPException(status_code=404, detail="Research mandate not found.")
        idea = queue_founder_idea(
            db,
            mandate,
            AlphaFounderResearchIdeaCreate(
                mandate_id=contract.mandate_id,
                expected_mandate_digest=contract.mandate_digest,
                idea=contract.research_idea,
                submitted_by="founder-operator",
                conversation_id=source.conversation_id,
                minimum_history_days=contract.minimum_history_days,
                maximum_variants=contract.maximum_variants,
                minimum_instruments=contract.minimum_instruments,
                maximum_instruments=contract.maximum_instruments,
                universe_selection_policy=contract.universe_selection_policy,
                universe_slices=contract.universe_slices,
            ),
        )
        task.status = "succeeded"
        task.started_at = task.completed_at = created_at
        task.result = {
            "founder_research_idea_id": str(idea.id),
            "idea_digest": idea.idea_digest,
            "status": idea.status,
            "authority": "no_capital_research",
        }
        append_task_event(
            db,
            task,
            "founder_research_idea_queued",
            "Research idea queued for independent RI and senior-researcher review.",
            payload=task.result,
        )
    proposal.status = "materialized"
    proposal.materialized_task_id = task.id
    proposal.decided_by = actor
    proposal.decision_reason = reason
    proposal.decided_at = created_at
    return task


def reject_proposal(
    proposal: FounderProposal,
    *,
    actor: str,
    reason: str,
    now: datetime | None = None,
) -> None:
    if proposal.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal is already {proposal.status}.",
        )
    proposal.status = "rejected"
    proposal.decided_by = actor
    proposal.decision_reason = reason
    proposal.decided_at = now or datetime.now(UTC)


def _task_create(
    proposed: ProposedTask,
    source: Task,
    actor: str,
    now: datetime,
) -> TaskCreate:
    suffix = uuid.uuid4().hex[:8].upper()
    return TaskCreate(
        task_number=f"PLANNED-{now:%Y%m%dT%H%M%S}-{suffix}",
        parent_task_id=source.id,
        created_by=actor,
        **proposed.model_dump(mode="python", exclude_none=True),
    )
