from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_mission_supervisor
from app.db.session import get_db
from app.models import EngineeringMission, TaskGraph
from app.schemas import MissionReconcileResponse, MissionResponse
from app.services.daily_research import reconcile_programs
from app.services.supervision import reconcile_mission
from app.services.task_graphs import reconcile_graph

router = APIRouter(
    prefix="/v1/supervisor",
    tags=["mission-supervisor"],
    dependencies=[Depends(require_mission_supervisor)],
)


@router.post("/reconcile", response_model=list[MissionReconcileResponse])
def reconcile_supervised_missions(
    db: Annotated[Session, Depends(get_db)],
) -> list[MissionReconcileResponse]:
    reconcile_programs(db)
    graphs = db.scalars(
        select(TaskGraph)
        .where(TaskGraph.status.in_(["active", "cancelling", "compensating"]))
        .order_by(TaskGraph.created_at)
        .with_for_update(skip_locked=True)
    ).all()
    for graph in graphs:
        reconcile_graph(db, graph)
    missions = db.scalars(
        select(EngineeringMission)
        .where(
            EngineeringMission.supervision_enabled.is_(True),
            EngineeringMission.supervision_status.in_(
                ["pending_approval", "active", "recovering", "attention_required"]
            ),
            or_(
                EngineeringMission.next_reconcile_at.is_(None),
                EngineeringMission.next_reconcile_at <= datetime.now(UTC),
            ),
        )
        .order_by(EngineeringMission.created_at)
        .with_for_update(skip_locked=True)
    ).all()
    results = []
    for mission in missions:
        action, task_id = reconcile_mission(db, mission)
        results.append(
            MissionReconcileResponse(
                mission=MissionResponse.model_validate(mission),
                action=action,
                task_id=task_id,
            )
        )
    db.commit()
    return results
