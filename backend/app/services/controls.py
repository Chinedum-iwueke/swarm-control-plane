from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Agent, ControlEvent, ControlScope

GLOBAL_SCOPE_KEY = "all"


def matching_control_scopes(db: Session, agent: Agent) -> list[ControlScope]:
    return list(
        db.scalars(
            select(ControlScope)
            .where(
                ControlScope.is_paused.is_(True),
                or_(
                    (ControlScope.scope_type == "global")
                    & (ControlScope.scope_key == GLOBAL_SCOPE_KEY),
                    (ControlScope.scope_type == "machine")
                    & (ControlScope.scope_key == agent.machine),
                    (ControlScope.scope_type == "agent")
                    & (ControlScope.scope_key == agent.slug),
                ),
            )
            .order_by(ControlScope.scope_type, ControlScope.scope_key)
        ).all()
    )


def set_control_scope(
    db: Session,
    *,
    scope_type: str,
    scope_key: str,
    paused: bool,
    reason: str,
    actor: str,
) -> tuple[ControlScope, ControlEvent]:
    scope = db.scalar(
        select(ControlScope)
        .where(
            ControlScope.scope_type == scope_type,
            ControlScope.scope_key == scope_key,
        )
        .with_for_update()
    )
    previous = scope.is_paused if scope is not None else False
    if scope is None:
        scope = ControlScope(
            scope_type=scope_type,
            scope_key=scope_key,
            is_paused=paused,
            reason=reason,
            updated_by=actor,
        )
        db.add(scope)
    else:
        scope.is_paused = paused
        scope.reason = reason
        scope.updated_by = actor

    event = ControlEvent(
        scope_type=scope_type,
        scope_key=scope_key,
        event_type="control_paused" if paused else "control_resumed",
        actor=actor,
        reason=reason,
        payload={"previous_paused": previous, "paused": paused},
    )
    db.add(event)
    db.flush()
    return scope, event
