from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import (
    Agent,
    OperationalNote,
    OperationalNoteEvent,
    PackageDeployment,
    RolePackage,
    Task,
)
from app.schemas.operational_note import (
    AgentOperationalNoteCreate,
    OperationalNoteCreate,
    OperationalNoteDetail,
    OperationalNoteEventResponse,
    OperationalNoteProposalRequest,
    OperationalNoteResponse,
    OperationalNoteTransition,
)
from app.schemas.task import TaskCreate, TaskResponse
from app.services.operational_notes import create_note, transition_note
from app.services.tasks import build_task, persist_new_task, serialize_task

router = APIRouter(
    prefix="/v1/operational-notes",
    tags=["operational-notes"],
    dependencies=[Depends(require_orchestrator)],
)
agent_router = APIRouter(prefix="/v1/agent/operational-notes", tags=["agent-notes"])


def _detail(db: Session, note: OperationalNote) -> OperationalNoteDetail:
    events = db.scalars(
        select(OperationalNoteEvent)
        .where(OperationalNoteEvent.note_id == note.id)
        .order_by(OperationalNoteEvent.created_at)
    ).all()
    return OperationalNoteDetail(
        **OperationalNoteResponse.model_validate(note).model_dump(),
        events=[OperationalNoteEventResponse.model_validate(item) for item in events],
    )


@router.post("", response_model=OperationalNoteResponse, status_code=201)
def record_note(
    payload: OperationalNoteCreate, db: Annotated[Session, Depends(get_db)]
):
    note = create_note(db, payload)
    db.commit()
    db.refresh(note)
    return OperationalNoteResponse.model_validate(note)


@router.get("", response_model=list[OperationalNoteResponse])
def list_notes(
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[str | None, Query(max_length=200)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    statement = select(OperationalNote)
    if status:
        statement = statement.where(OperationalNote.status == status)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                OperationalNote.subject.ilike(pattern),
                OperationalNote.finding.ilike(pattern),
                OperationalNote.note_key.ilike(pattern),
            )
        )
    records = db.scalars(
        statement.order_by(OperationalNote.updated_at.desc()).limit(limit)
    ).all()
    return [OperationalNoteResponse.model_validate(item) for item in records]


@router.get("/{note_id}", response_model=OperationalNoteDetail)
def get_note(note_id: UUID, db: Annotated[Session, Depends(get_db)]):
    note = db.get(OperationalNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Operational note not found.")
    return _detail(db, note)


@router.post("/{note_id}/transitions", response_model=OperationalNoteDetail)
def update_note(
    note_id: UUID,
    payload: OperationalNoteTransition,
    db: Annotated[Session, Depends(get_db)],
):
    note = db.scalar(
        select(OperationalNote).where(OperationalNote.id == note_id).with_for_update()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Operational note not found.")
    transition_note(db, note, payload)
    db.commit()
    db.refresh(note)
    return _detail(db, note)


@router.post("/{note_id}/proposal-request", response_model=TaskResponse)
def request_note_proposal(
    note_id: UUID,
    payload: OperationalNoteProposalRequest,
    db: Annotated[Session, Depends(get_db)],
):
    note = db.get(OperationalNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Operational note not found.")
    task_number = f"NOTE-{note.id.hex[:12]}"
    existing = db.scalar(select(Task).where(Task.task_number == task_number))
    if existing is not None:
        return TaskResponse.model_validate(serialize_task(existing))
    task = build_task(
        TaskCreate(
            task_number=task_number,
            project="swarm-control-plane",
            task_type="founder_request",
            title=f"Plan remediation: {note.subject}",
            objective=payload.objective,
            priority={"low": 35, "medium": 50, "high": 70, "critical": 90}[
                note.urgency
            ],
            risk_level=0,
            created_by=payload.requested_by,
            input_contract={
                "request": payload.objective,
                "source": "operational_note",
                "operational_note_id": str(note.id),
                "operational_note_digest": note.record_digest,
            },
            expected_outputs=["structured founder proposal"],
            acceptance_criteria=[
                "The proposal remains inside the normal founder approval boundary.",
                "The operational note digest is retained as source provenance.",
            ],
            approval_policy={"kind": "founder_proposal"},
            required_capabilities=["founder-intake"],
            allowed_machines=["vm1-developer"],
            max_attempts=1,
        )
    )
    persist_new_task(db, task)
    db.commit()
    db.refresh(task)
    return TaskResponse.model_validate(serialize_task(task))


def _require_steward(db: Session, agent: Agent) -> None:
    capability = "operational-memory"
    if capability not in agent.capabilities:
        raise HTTPException(status_code=403, detail="Agent lacks required capability.")
    package = db.scalar(
        select(RolePackage)
        .join(PackageDeployment, PackageDeployment.package_id == RolePackage.id)
        .where(
            PackageDeployment.agent_id == agent.id,
            PackageDeployment.is_active.is_(True),
            RolePackage.name == "vm1-operational-memory-steward",
        )
    )
    if package is None or capability not in package.manifest.get(
        "required_capabilities", []
    ):
        raise HTTPException(
            status_code=409, detail="Operational-memory role package is not active."
        )


@agent_router.post("", response_model=OperationalNoteResponse, status_code=201)
def record_agent_note(
    payload: AgentOperationalNoteCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_steward(db, agent)
    note = create_note(
        db,
        OperationalNoteCreate(
            **payload.model_dump(mode="python"), created_by=agent.slug
        ),
    )
    db.commit()
    db.refresh(note)
    return OperationalNoteResponse.model_validate(note)
