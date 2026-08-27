from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    CanonicalEvidenceEdge,
    CanonicalEvidenceObject,
    EvidenceLifecycleState,
    Task,
)
from app.models.agent_context import AgentContextManifest, AgentWorkingMemoryReceipt
from app.schemas.agent_context import AgentContextCreate, WorkingMemoryCreate

SCHEMA_VERSION = "agent-context-manifest-v1.0.0"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def create_context(db: Session, request: AgentContextCreate) -> AgentContextManifest:
    now = datetime.now(UTC)
    task = db.get(Task, request.task_id)
    agent = db.get(Agent, request.agent_id)
    if task is None or agent is None:
        raise HTTPException(404, "Task or agent not found.")
    if request.expires_at <= now:
        raise HTTPException(422, "Context expiry must be in the future.")
    if request.attempt_number != task.attempt_count + 1:
        raise HTTPException(409, "Context must bind the next unconsumed task attempt.")
    if task.assigned_agent_id not in (None, agent.id):
        raise HTTPException(409, "Task is assigned to another agent.")
    from app.services.tasks import resolve_task_authority

    authority = resolve_task_authority(db, task, agent, now)
    if not authority or not all(item["allowed"] for item in authority):
        raise HTTPException(
            403, "Active agent authority does not cover this task context."
        )
    authorization_snapshot_digest = digest(authority)

    object_ids = [item.object_id for item in request.sources]
    records = {
        item.id: item
        for item in db.scalars(
            select(CanonicalEvidenceObject).where(
                CanonicalEvidenceObject.id.in_(object_ids)
            )
        )
    }
    if any(object_id not in records for object_id in object_ids):
        raise HTTPException(404, "One or more context sources were not found.")
    lifecycle = {
        item.object_id: item
        for item in db.scalars(
            select(EvidenceLifecycleState).where(
                EvidenceLifecycleState.object_id.in_(object_ids)
            )
        )
    }
    oppositions = list(
        db.scalars(
            select(CanonicalEvidenceEdge).where(
                CanonicalEvidenceEdge.predicate == "contradicts",
                CanonicalEvidenceEdge.subject_id.in_(object_ids),
                CanonicalEvidenceEdge.object_id.in_(object_ids),
            )
        )
    )
    contradiction_map: dict[UUID, list[str]] = {}
    for edge in oppositions:
        contradiction_map.setdefault(edge.subject_id, []).append(str(edge.object_id))
        contradiction_map.setdefault(edge.object_id, []).append(str(edge.subject_id))

    allowed_access = task.input_contract.get(
        "context_access_classes", ["public", "internal"]
    )
    if not isinstance(allowed_access, list) or not set(allowed_access).issubset(
        {"public", "internal", "restricted"}
    ):
        raise HTTPException(422, "Task context access classes are invalid.")

    items: list[dict] = []
    for source in sorted(request.sources, key=lambda item: item.prompt_position):
        record = records[source.object_id]
        state = lifecycle.get(record.id)
        if state is None or not state.active_for_retrieval:
            raise HTTPException(409, f"Context source {record.id} is not active.")
        if record.access_class == "protected":
            raise HTTPException(
                403,
                "Protected evidence requires a separately approved disclosure path.",
            )
        if record.access_class not in allowed_access:
            raise HTTPException(403, "Context source exceeds the task access boundary.")
        if record.project != task.project and record.project not in {
            "systematic-research",
            "invariance-research",
        }:
            raise HTTPException(
                422, "Context source is outside the task project boundary."
            )
        excerpt = json.dumps(
            record.payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )[:4000]
        item_expiry = (
            min(request.expires_at, task.deadline_at)
            if getattr(task, "deadline_at", None)
            else request.expires_at
        )
        items.append(
            {
                "object_id": str(record.id),
                "object_type": record.object_type,
                "content_digest": record.content_digest,
                "access_class": record.access_class,
                "selection_reason": source.selection_reason,
                "sensitivity": record.access_class,
                "expires_at": item_expiry.isoformat(),
                "prompt_position": source.prompt_position,
                "excerpt": excerpt,
                "citation": {
                    "replay_path": f"/v1/research/evidence/{record.id}",
                    "coordinates": record.payload.get("coordinates"),
                    "contradicts": sorted(contradiction_map.get(record.id, [])),
                },
            }
        )
    pack = {
        "schema_version": SCHEMA_VERSION,
        "purpose": request.purpose,
        "items": items,
    }
    pack_digest = digest(pack)
    byte_count = len(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode())
    if byte_count > request.max_bytes:
        raise HTTPException(413, "Context pack exceeds the approved byte budget.")
    manifest_document = {
        "task_id": str(task.id),
        "agent_id": str(agent.id),
        "attempt_number": request.attempt_number,
        "authorization_snapshot_digest": authorization_snapshot_digest,
        "context_pack_digest": pack_digest,
        "expires_at": request.expires_at.isoformat(),
    }
    record = AgentContextManifest(
        task_id=task.id,
        agent_id=agent.id,
        attempt_number=request.attempt_number,
        schema_version=SCHEMA_VERSION,
        purpose=request.purpose,
        authorization_snapshot_digest=authorization_snapshot_digest,
        context_pack=pack,
        context_pack_digest=pack_digest,
        manifest_digest=digest(manifest_document),
        item_count=len(items),
        byte_count=byte_count,
        status="locked",
        expires_at=request.expires_at,
        created_by=request.created_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def serialize_context(record: AgentContextManifest) -> dict:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "agent_id": record.agent_id,
        "attempt_number": record.attempt_number,
        "schema_version": record.schema_version,
        "purpose": record.purpose,
        "authorization_snapshot_digest": record.authorization_snapshot_digest,
        "items": record.context_pack["items"],
        "context_pack_digest": record.context_pack_digest,
        "manifest_digest": record.manifest_digest,
        "item_count": record.item_count,
        "byte_count": record.byte_count,
        "status": record.status,
        "expires_at": record.expires_at,
        "created_by": record.created_by,
        "created_at": record.created_at,
    }


def active_context(db: Session, task: Task, agent: Agent) -> AgentContextManifest:
    record = db.scalar(
        select(AgentContextManifest).where(
            AgentContextManifest.task_id == task.id,
            AgentContextManifest.attempt_number == task.attempt_count,
        )
    )
    if record is None:
        raise HTTPException(404, "No context manifest is bound to this task attempt.")
    if (
        record.agent_id != agent.id
        or record.status != "locked"
        or record.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(409, "Context manifest is not active for this agent lease.")
    if digest(record.context_pack) != record.context_pack_digest:
        raise HTTPException(409, "Context pack integrity check failed.")
    return record


def record_working_memory(
    db: Session, context: AgentContextManifest, request: WorkingMemoryCreate
) -> AgentWorkingMemoryReceipt:
    if request.expires_at > context.expires_at or request.expires_at <= datetime.now(
        UTC
    ):
        raise HTTPException(
            422,
            "Working memory expiry must be active and no later than context expiry.",
        )
    document = {
        "context_manifest_digest": context.manifest_digest,
        "sequence": request.sequence,
        "kind": request.kind,
        "content_digest": request.content_digest,
        "workspace_path": request.workspace_path,
        "sensitivity": request.sensitivity,
        "expires_at": request.expires_at.isoformat(),
    }
    receipt = AgentWorkingMemoryReceipt(
        context_manifest_id=context.id,
        task_id=context.task_id,
        agent_id=context.agent_id,
        sequence=request.sequence,
        kind=request.kind,
        content_digest=request.content_digest,
        workspace_path=request.workspace_path,
        sensitivity=request.sensitivity,
        status="active",
        expires_at=request.expires_at,
        receipt_digest=digest(document),
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def discard_working_memory(db: Session, task_id: UUID, *, commit: bool = False) -> int:
    now = datetime.now(UTC)
    records = list(
        db.scalars(
            select(AgentWorkingMemoryReceipt).where(
                AgentWorkingMemoryReceipt.task_id == task_id,
                AgentWorkingMemoryReceipt.status == "active",
            )
        )
    )
    for record in records:
        record.status = "discarded"
        record.discarded_at = now
    if commit:
        db.commit()
    return len(records)
