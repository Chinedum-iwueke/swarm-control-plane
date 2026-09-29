from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.research_utilization import (
    ResearchUtilizationSnapshotCreate,
    ResearchUtilizationSnapshotResponse,
)
from app.services.research_utilization import current_status, record_snapshot

router = APIRouter(
    prefix="/v1/research/utilization",
    tags=["research-utilization"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/snapshots",
    response_model=ResearchUtilizationSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    payload: ResearchUtilizationSnapshotCreate,
    db: Annotated[Session, Depends(get_db)],
):
    if abs((datetime.now(UTC) - payload.observed_at).total_seconds()) > 300:
        raise HTTPException(
            status_code=422,
            detail="Utilization snapshot clock skew exceeds five minutes.",
        )
    return record_snapshot(db, payload)


@router.get("/current")
def current(
    db: Annotated[Session, Depends(get_db)],
    machine: Annotated[str | None, Query(pattern=r"^[a-z0-9-]+$")] = None,
):
    return current_status(db, machine)
