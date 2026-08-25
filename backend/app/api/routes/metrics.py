from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import (
    Agent,
    CanonicalEvidenceObject,
    ControlScope,
    CorpusBackup,
    CorpusRecoveryRun,
    CorpusSecurityFinding,
    ScientificIngestionJob,
    Task,
)
from app.models.fleet import FleetIncident, MachineObservation
from app.models.observability import RoutedServiceAlert, ServiceSLOState
from app.models.retrieval import EvidenceRetrievalState

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
CORPUS_INGESTION = Gauge(
    "hermes_corpus_ingestion_jobs", "Corpus ingestion jobs by status", ["status"]
)
CORPUS_SECURITY = Gauge(
    "hermes_corpus_security_findings", "Corpus security findings by code", ["code"]
)
CORPUS_PROJECTION_AGE = Gauge(
    "hermes_corpus_projection_age_seconds", "Age of the canonical corpus projection"
)
CORPUS_BACKUP_AGE = Gauge(
    "hermes_corpus_latest_backup_age_seconds", "Age of the latest corpus backup"
)
CORPUS_RESTORE_AGE = Gauge(
    "hermes_corpus_latest_restore_age_seconds", "Age of the latest corpus restore proof"
)
CORPUS_OBJECTS = Gauge(
    "hermes_corpus_canonical_objects", "Canonical corpus object count"
)
CORPUS_STORAGE = Gauge(
    "hermes_corpus_artifact_bytes", "Bytes referenced by canonical corpus artifacts"
)
FLEET_INCIDENTS = Gauge(
    "hermes_fleet_incidents",
    "Fleet incidents by machine and state",
    ["machine", "state"],
)
FLEET_SAMPLE_AGE = Gauge(
    "hermes_fleet_sample_age_seconds", "Age of latest fleet sample", ["machine"]
)
SERVICE_SLO = Gauge(
    "hermes_service_slo_state",
    "Service SLO state (1 for current state)",
    ["service", "indicator", "status"],
)
ROUTED_ALERTS = Gauge(
    "hermes_routed_service_alerts",
    "Routed service alerts by state and severity",
    ["state", "severity"],
)

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
    FLEET_INCIDENTS.clear()
    for machine, state, count in db.execute(
        select(FleetIncident.machine, FleetIncident.state, func.count()).group_by(
            FleetIncident.machine, FleetIncident.state
        )
    ).all():
        FLEET_INCIDENTS.labels(machine=machine, state=state).set(count)
    FLEET_SAMPLE_AGE.clear()
    for machine, observed_at in db.execute(
        select(
            MachineObservation.machine,
            func.max(MachineObservation.observed_at),
        ).group_by(MachineObservation.machine)
    ).all():
        FLEET_SAMPLE_AGE.labels(machine=machine).set(
            max(0.0, (now - observed_at).total_seconds())
        )
    SERVICE_SLO.clear()
    for service, indicator, status in db.execute(
        select(ServiceSLOState.service_key, ServiceSLOState.indicator, ServiceSLOState.status)
    ).all():
        SERVICE_SLO.labels(service=service, indicator=indicator, status=status).set(1)
    ROUTED_ALERTS.clear()
    for state, severity, count in db.execute(
        select(RoutedServiceAlert.state, RoutedServiceAlert.severity, func.count()).group_by(
            RoutedServiceAlert.state, RoutedServiceAlert.severity
        )
    ).all():
        ROUTED_ALERTS.labels(state=state, severity=severity).set(count)
    PAUSED_SCOPES.clear()
    for scope_type, count in db.execute(
        select(ControlScope.scope_type, func.count())
        .where(ControlScope.is_paused)
        .group_by(ControlScope.scope_type)
    ).all():
        PAUSED_SCOPES.labels(scope_type=scope_type).set(count)

    CORPUS_INGESTION.clear()
    for job_status, count in db.execute(
        select(ScientificIngestionJob.status, func.count()).group_by(
            ScientificIngestionJob.status
        )
    ).all():
        CORPUS_INGESTION.labels(status=job_status).set(count)
    CORPUS_SECURITY.clear()
    for code, count in db.execute(
        select(CorpusSecurityFinding.finding_code, func.count()).group_by(
            CorpusSecurityFinding.finding_code
        )
    ).all():
        CORPUS_SECURITY.labels(code=code).set(count)
    projection_built_at = db.scalar(
        select(func.max(EvidenceRetrievalState.built_at))
    )
    latest_backup_at = db.scalar(select(func.max(CorpusBackup.created_at)))
    latest_restore_at = db.scalar(
        select(func.max(CorpusRecoveryRun.ended_at)).where(
            CorpusRecoveryRun.operation == "restore",
            CorpusRecoveryRun.status == "succeeded",
        )
    )
    CORPUS_PROJECTION_AGE.set(
        max(0.0, (now - projection_built_at).total_seconds())
        if projection_built_at
        else -1
    )
    CORPUS_BACKUP_AGE.set(
        max(0.0, (now - latest_backup_at).total_seconds())
        if latest_backup_at
        else -1
    )
    CORPUS_RESTORE_AGE.set(
        max(0.0, (now - latest_restore_at).total_seconds())
        if latest_restore_at
        else -1
    )
    CORPUS_OBJECTS.set(
        db.scalar(select(func.count()).select_from(CanonicalEvidenceObject)) or 0
    )
    artifact_bytes = db.scalars(
        select(CanonicalEvidenceObject.payload).where(
            CanonicalEvidenceObject.object_type == "artifact"
        )
    ).all()
    CORPUS_STORAGE.set(sum(int(item.get("byte_size", 0)) for item in artifact_bytes))

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
