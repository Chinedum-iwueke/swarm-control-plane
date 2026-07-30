from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import Agent, ControlScope, Task

TASKS = Gauge("hermes_tasks", "Tasks by status", ["status"])
AGENTS = Gauge("hermes_agents", "Agents by enabled and online state", ["state"])
AGENT_INFO = Gauge(
    "hermes_agent_info",
    "Registered agent runtime information",
    ["slug", "machine", "runtime_version"],
)
ACTIVE_LEASES = Gauge("hermes_active_leases", "Tasks with active leases")
OLDEST_LEASE_AGE = Gauge(
    "hermes_oldest_active_lease_age_seconds",
    "Age of the oldest active task lease",
)
PAUSED_SCOPES = Gauge("hermes_paused_scopes", "Paused control scopes", ["scope_type"])

router = APIRouter(
    prefix="/v1/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("", response_class=Response)
def metrics(db: Annotated[Session, Depends(get_db)]) -> Response:
    TASKS.clear()
    for status, count in db.execute(
        select(Task.status, func.count()).group_by(Task.status)
    ).all():
        TASKS.labels(status=status).set(count)

    now = datetime.now(UTC)
    online_cutoff = now - timedelta(seconds=90)
    AGENTS.clear()
    AGENTS.labels(state="enabled").set(
        db.scalar(select(func.count()).select_from(Agent).where(Agent.is_enabled)) or 0
    )
    AGENTS.labels(state="online").set(
        db.scalar(
            select(func.count())
            .select_from(Agent)
            .where(
                Agent.is_enabled,
                Agent.last_heartbeat_at.is_not(None),
                Agent.last_heartbeat_at >= online_cutoff,
            )
        )
        or 0
    )
    AGENT_INFO.clear()
    for slug, machine, runtime_version in db.execute(
        select(Agent.slug, Agent.machine, Agent.runtime_version).where(
            Agent.is_enabled
        )
    ).all():
        AGENT_INFO.labels(
            slug=slug,
            machine=machine,
            runtime_version=runtime_version or "unknown",
        ).set(1)
    ACTIVE_LEASES.set(
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.status.in_(("leased", "running")))
        )
        or 0
    )
    oldest_lease = db.scalar(
        select(func.min(Task.leased_at)).where(
            Task.status.in_(("leased", "running")),
            Task.leased_at.is_not(None),
        )
    )
    OLDEST_LEASE_AGE.set(
        max(0.0, (now - oldest_lease).total_seconds()) if oldest_lease else 0
    )
    PAUSED_SCOPES.clear()
    for scope_type, count in db.execute(
        select(ControlScope.scope_type, func.count())
        .where(ControlScope.is_paused)
        .group_by(ControlScope.scope_type)
    ).all():
        PAUSED_SCOPES.labels(scope_type=scope_type).set(count)

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
