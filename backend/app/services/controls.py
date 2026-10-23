from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Agent, ControlEvent, ControlScope, Task

GLOBAL_SCOPE_KEY = "all"
AUTONOMOUS_RESEARCH_SCOPE_KEY = "autonomous-research"
AUTONOMOUS_RESEARCH_TASK_TYPES = {
    "alpha_data_admission",
    "alpha_discovery",
    "alpha_research_execution",
    "alpha_strategy_review",
    "founder_hypothesis_intake",
}


def task_matches_control_scope(scope: ControlScope, task: Task) -> bool:
    if (
        scope.scope_type != "workflow"
        or scope.scope_key != AUTONOMOUS_RESEARCH_SCOPE_KEY
    ):
        return False
    if task.task_type in AUTONOMOUS_RESEARCH_TASK_TYPES:
        return True
    return (
        task.task_type == "engineering_mission"
        and task.project == "bulletproof_bt"
        and task.created_by == "alpha-campaign-director"
    )


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


def paused_workflow_scopes(db: Session) -> list[ControlScope]:
    return list(
        db.scalars(
            select(ControlScope)
            .where(
                ControlScope.is_paused.is_(True),
                ControlScope.scope_type == "workflow",
            )
            .order_by(ControlScope.scope_key)
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
