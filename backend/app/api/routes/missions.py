from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import EngineeringMission, MissionEvent, Task, TaskDependency
from app.schemas import MissionCreate, MissionDetailResponse, MissionResponse
from app.services.missions import (
    create_mission,
    refresh_mission,
    verify_mission_approval,
)
from app.services.tasks import serialize_task

router = APIRouter(
    prefix="/v1/missions",
    tags=["engineering-missions"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def submit_mission(
    payload: MissionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> MissionResponse:
    verify_mission_approval(
        payload.manifest,
        payload.approval_signature,
        get_settings().mission_approval_secret,
    )
    try:
        mission = create_mission(
            db,
            payload.manifest,
            payload.created_by,
            payload.approval_signature,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Milestone ID or mission task already exists."
        ) from exc
    db.refresh(mission)
    return MissionResponse.model_validate(mission)


@router.get("", response_model=list[MissionResponse])
def list_missions(
    db: Annotated[Session, Depends(get_db)],
) -> list[MissionResponse]:
    missions = db.scalars(
        select(EngineeringMission).order_by(EngineeringMission.created_at.desc())
    ).all()
    return [MissionResponse.model_validate(item) for item in missions]


@router.get("/{mission_id}", response_model=MissionDetailResponse)
def get_mission(
    mission_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> MissionDetailResponse:
    mission = db.get(EngineeringMission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found.")
    refresh_mission(db, mission.id)
    db.commit()
    db.refresh(mission)
    tasks = db.scalars(
        select(Task).where(Task.mission_id == mission.id).order_by(Task.created_at)
    ).all()
    dependencies = db.scalars(
        select(TaskDependency)
        .join(Task, Task.id == TaskDependency.task_id)
        .where(Task.mission_id == mission.id)
    ).all()
    events = db.scalars(
        select(MissionEvent)
        .where(MissionEvent.mission_id == mission.id)
        .order_by(MissionEvent.id)
    ).all()
    return MissionDetailResponse(
        mission=MissionResponse.model_validate(mission),
        tasks=[serialize_task(task) for task in tasks],
        dependencies=[
            {
                "task_id": str(item.task_id),
                "depends_on_task_id": str(item.depends_on_task_id),
            }
            for item in dependencies
        ],
        events=[
            {
                "id": item.id,
                "event_type": item.event_type,
                "actor": item.actor,
                "message": item.message,
                "payload": item.payload,
                "created_at": item.created_at,
            }
            for item in events
        ],
    )
