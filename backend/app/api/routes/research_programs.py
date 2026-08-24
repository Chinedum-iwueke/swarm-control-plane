from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import ResearchDailyCycle, ResearchProgram
from app.schemas.research_program import (
    DailyResearchDigest,
    ResearchCycleApproval,
    ResearchCycleEventResponse,
    ResearchCycleLink,
    ResearchDailyCycleResponse,
    ResearchProgramCreate,
    ResearchProgramResponse,
    WeeklyResearchMetrics,
)
from app.services.daily_research import (
    create_program,
    cycle_events,
    daily_digest,
    decide_cycle,
    link_cycle,
    reconcile_programs,
    weekly_metrics,
)

router = APIRouter(
    prefix="/v1/research-programs",
    tags=["daily-research"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=ResearchProgramResponse, status_code=201)
def register_program(
    payload: ResearchProgramCreate, db: Annotated[Session, Depends(get_db)]
):
    return ResearchProgramResponse.model_validate(create_program(db, payload))


@router.get("", response_model=list[ResearchProgramResponse])
def list_programs(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(ResearchProgram).order_by(ResearchProgram.created_at)
    ).all()
    return [ResearchProgramResponse.model_validate(item) for item in records]


@router.get("/cycles", response_model=list[ResearchDailyCycleResponse])
def list_cycles(db: Annotated[Session, Depends(get_db)], limit: int = 30):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    records = db.scalars(
        select(ResearchDailyCycle)
        .order_by(ResearchDailyCycle.created_at.desc())
        .limit(limit)
    ).all()
    return [ResearchDailyCycleResponse.model_validate(item) for item in records]


@router.post("/cycles/{cycle_id}/link", response_model=ResearchDailyCycleResponse)
def bind_cycle(
    cycle_id: UUID,
    payload: ResearchCycleLink,
    db: Annotated[Session, Depends(get_db)],
):
    cycle = db.get(ResearchDailyCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Research cycle not found.")
    return ResearchDailyCycleResponse.model_validate(link_cycle(db, cycle, payload))


@router.post("/cycles/{cycle_id}/decision", response_model=ResearchDailyCycleResponse)
def decide_daily_question(
    cycle_id: UUID,
    payload: ResearchCycleApproval,
    db: Annotated[Session, Depends(get_db)],
):
    cycle = db.scalar(
        select(ResearchDailyCycle)
        .where(ResearchDailyCycle.id == cycle_id)
        .with_for_update()
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Research cycle not found.")
    return ResearchDailyCycleResponse.model_validate(decide_cycle(db, cycle, payload))


@router.get(
    "/cycles/{cycle_id}/events", response_model=list[ResearchCycleEventResponse]
)
def read_cycle_events(cycle_id: UUID, db: Annotated[Session, Depends(get_db)]):
    if db.get(ResearchDailyCycle, cycle_id) is None:
        raise HTTPException(status_code=404, detail="Research cycle not found.")
    return [
        ResearchCycleEventResponse.model_validate(item)
        for item in cycle_events(db, cycle_id)
    ]


@router.post("/reconcile", response_model=list[ResearchDailyCycleResponse])
def reconcile_daily_research(db: Annotated[Session, Depends(get_db)]):
    records = reconcile_programs(db)
    db.commit()
    return [ResearchDailyCycleResponse.model_validate(item) for item in records]


@router.get("/digest/{day}", response_model=DailyResearchDigest)
def get_daily_digest(day: date, db: Annotated[Session, Depends(get_db)]):
    return DailyResearchDigest.model_validate(daily_digest(db, day))


@router.get("/weekly/{week_start}", response_model=WeeklyResearchMetrics)
def get_weekly_metrics(week_start: date, db: Annotated[Session, Depends(get_db)]):
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    if week_start > datetime.now(UTC).date() + timedelta(days=7):
        raise HTTPException(
            status_code=422, detail="week_start is too far in the future"
        )
    return WeeklyResearchMetrics.model_validate(weekly_metrics(db, week_start))
