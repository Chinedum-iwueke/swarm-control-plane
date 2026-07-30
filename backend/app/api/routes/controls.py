from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import ControlEvent, ControlScope
from app.schemas import (
    ControlEventResponse,
    ControlMutation,
    ControlMutationResponse,
    ControlScopeResponse,
)
from app.services.controls import GLOBAL_SCOPE_KEY, set_control_scope

router = APIRouter(
    prefix="/v1/control",
    tags=["control"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/scopes", response_model=list[ControlScopeResponse])
def list_control_scopes(
    db: Annotated[Session, Depends(get_db)],
) -> list[ControlScopeResponse]:
    scopes = db.scalars(
        select(ControlScope).order_by(
            ControlScope.scope_type, ControlScope.scope_key
        )
    ).all()
    return [ControlScopeResponse.model_validate(scope) for scope in scopes]


@router.get("/events", response_model=list[ControlEventResponse])
def list_control_events(
    db: Annotated[Session, Depends(get_db)],
) -> list[ControlEventResponse]:
    events = db.scalars(
        select(ControlEvent).order_by(ControlEvent.id.desc()).limit(500)
    ).all()
    return [ControlEventResponse.model_validate(event) for event in events]


@router.post("/pause", response_model=ControlMutationResponse)
def pause_control_scope(
    payload: ControlMutation,
    db: Annotated[Session, Depends(get_db)],
) -> ControlMutationResponse:
    return _mutate(payload, db, paused=True)


@router.post("/resume", response_model=ControlMutationResponse)
def resume_control_scope(
    payload: ControlMutation,
    db: Annotated[Session, Depends(get_db)],
) -> ControlMutationResponse:
    return _mutate(payload, db, paused=False)


def _mutate(
    payload: ControlMutation,
    db: Session,
    *,
    paused: bool,
) -> ControlMutationResponse:
    scope_key = (
        GLOBAL_SCOPE_KEY if payload.scope_type == "global" else payload.scope_key
    )
    scope, event = set_control_scope(
        db,
        scope_type=payload.scope_type,
        scope_key=scope_key,
        paused=paused,
        reason=payload.reason,
        actor=payload.actor,
    )
    db.commit()
    db.refresh(scope)
    db.refresh(event)
    return ControlMutationResponse(
        scope=ControlScopeResponse.model_validate(scope),
        event=ControlEventResponse.model_validate(event),
    )
