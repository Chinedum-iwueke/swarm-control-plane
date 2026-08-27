from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Agent,
    AgentCapabilityGrant,
    CanonicalEvidenceObject,
    EvidenceLifecycleState,
)
from app.schemas.agent_context import (
    AgentContextCreate,
    ContextSource,
    WorkingMemoryCreate,
)
from app.schemas.task import TaskCreate
from app.services.agent_context import (
    create_context,
    digest,
    discard_working_memory,
    record_working_memory,
)
from app.services.tasks import build_task


def main() -> int:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        grant = db.scalar(
            select(AgentCapabilityGrant)
            .where(
                AgentCapabilityGrant.status == "active",
                AgentCapabilityGrant.expires_at > now,
            )
            .order_by(AgentCapabilityGrant.created_at)
        )
        if grant is None:
            raise RuntimeError("No active agent capability grant is available.")
        agent = db.get(Agent, grant.agent_id)
        if agent is None:
            raise RuntimeError("Granted agent is unavailable.")
        source = db.scalar(
            select(CanonicalEvidenceObject)
            .join(
                EvidenceLifecycleState,
                EvidenceLifecycleState.object_id == CanonicalEvidenceObject.id,
            )
            .where(
                EvidenceLifecycleState.state == "active",
                CanonicalEvidenceObject.access_class.in_(["public", "internal"]),
                CanonicalEvidenceObject.project.in_(
                    [
                        grant.repositories[0],
                        "systematic-research",
                        "invariance-research",
                    ]
                ),
            )
            .limit(1)
        )
        if source is None:
            raise RuntimeError("No admissible canonical evidence source is available.")
        task = build_task(
            TaskCreate(
                task_number=f"AGT002-PILOT-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}",
                project=grant.repositories[0],
                task_type=grant.task_types[0],
                title="AGT-002 no-execution context replay pilot",
                objective="Prove exact governed context replay and ephemeral scratch disposal without executing work.",
                risk_level=0,
                created_by="agt002-pilot",
                input_contract={
                    "governed_context_required": True,
                    "pilot": "AGT-002",
                    "workflow": "no-execution",
                },
                expected_outputs=[
                    "context manifest",
                    "working-memory disposal receipt",
                ],
                acceptance_criteria=[
                    "Exact pack digest replays",
                    "Scratch receipt is discarded",
                ],
                required_capabilities=[grant.capability],
                allowed_machines=["agt002-no-execution-pilot"],
                max_attempts=1,
            )
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        context = create_context(
            db,
            AgentContextCreate(
                task_id=task.id,
                agent_id=agent.id,
                attempt_number=1,
                purpose="No-execution proof of provenance-bearing agent context.",
                sources=[
                    ContextSource(
                        object_id=source.id,
                        selection_reason="Live canonical evidence replay fixture.",
                        prompt_position=0,
                    )
                ],
                expires_at=now + timedelta(minutes=15),
                created_by="agt002-pilot",
            ),
        )
        memory = record_working_memory(
            db,
            context,
            WorkingMemoryCreate(
                lease_token="agt002-pilot-no-runtime-lease-token",
                sequence=1,
                kind="scratch",
                content_digest=digest(
                    {"pilot": "ephemeral scratch was kept outside the control plane"}
                ),
                workspace_path="scratch/agt002-pilot.json",
                sensitivity="internal",
                expires_at=now + timedelta(minutes=10),
            ),
        )
        discarded = discard_working_memory(db, task.id)
        task.status = "cancelled"
        task.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(memory)
        report = {
            "schema_version": "agt002-pilot-report-v1.0.0",
            "success": True,
            "capital_or_execution_authority": False,
            "task_id": str(task.id),
            "task_status": task.status,
            "agent_id": str(agent.id),
            "source_object_id": str(source.id),
            "authorization_snapshot_digest": context.authorization_snapshot_digest,
            "context_pack_digest": context.context_pack_digest,
            "manifest_digest": context.manifest_digest,
            "exact_replay": digest(context.context_pack) == context.context_pack_digest,
            "working_memory_content_stored": False,
            "working_memory_receipt_digest": memory.receipt_digest,
            "working_memory_status": memory.status,
            "working_memory_discarded": discarded,
        }
        report["report_digest"] = digest(report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
