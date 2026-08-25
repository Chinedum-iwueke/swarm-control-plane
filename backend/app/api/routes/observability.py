from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.observability import AlertRoutingEvent, RoutedServiceAlert
from app.schemas.observability import AlertAction, ObservabilityEvaluationRequest
from app.services.observability import evaluate_observability, transition_alert

router = APIRouter(
    prefix="/v1/observability",
    tags=["observability"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/overview")
def overview(db: Annotated[Session, Depends(get_db)]):
    return evaluate_observability(db)


@router.post("/evaluate")
def evaluate(
    payload: ObservabilityEvaluationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return evaluate_observability(db, payload.observed_at or datetime.now(UTC))


@router.post("/alerts/{alert_id}")
def act_on_alert(
    alert_id: UUID,
    payload: AlertAction,
    db: Annotated[Session, Depends(get_db)],
):
    alert = db.get(RoutedServiceAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Service alert not found.")
    try:
        return transition_alert(db, alert, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/alerts/{alert_id}/events")
def alert_events(alert_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(AlertRoutingEvent)
            .where(AlertRoutingEvent.alert_id == alert_id)
            .order_by(AlertRoutingEvent.sequence)
        ).all()
    )
