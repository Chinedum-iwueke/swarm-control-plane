from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FounderNotification
from app.models.fleet import FleetIncident, FleetIncidentEvent, MachineObservation
from app.schemas.fleet import IncidentAction, MachineObservationCreate
from app.services.founder_notifications import _insert_once

BREACH_SAMPLES = 3
RECOVERY_SAMPLES = 3
STALE_AFTER = timedelta(seconds=90)
THRESHOLDS = {
    "cpu_saturation": ("cpu_utilization_percent", 95.0, "high"),
    "memory_pressure": ("memory_available_percent", 10.0, "low"),
    "swap_thrashing": ("swap_out_bytes_delta", 64 * 1024 * 1024, "high"),
    "disk_capacity": ("disk_used_percent", 90.0, "high"),
    "inode_capacity": ("inode_used_percent", 90.0, "high"),
    "cpu_pressure": ("cpu_pressure_avg10", 25.0, "high"),
    "io_pressure": ("io_pressure_avg10", 20.0, "high"),
    "memory_psi": ("memory_pressure_avg10", 10.0, "high"),
    "oom_kill": ("oom_kills_delta", 1.0, "high"),
}


def record_observation(
    db: Session, agent_id: UUID, payload: MachineObservationCreate
) -> MachineObservation:
    existing = db.scalar(
        select(MachineObservation).where(
            MachineObservation.machine == payload.machine,
            MachineObservation.sample_id == payload.sample_id,
        )
    )
    if existing is not None:
        return existing
    document = payload.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    observation = MachineObservation(
        agent_id=agent_id,
        machine=payload.machine,
        sample_id=payload.sample_id,
        observed_at=payload.observed_at,
        metrics=payload.metrics.model_dump(),
        service_health={item.name: item.status for item in payload.services},
        record_digest=digest,
        retention_class="telemetry_raw_30d",
    )
    db.add(observation)
    db.flush()
    evaluate_observation(db, observation)
    evaluate_staleness(db, datetime.now(UTC))
    db.commit()
    db.refresh(observation)
    return observation


def evaluate_observation(db: Session, observation: MachineObservation) -> None:
    signals: dict[str, tuple[bool, str, dict]] = {}
    for signal, (field, threshold, direction) in THRESHOLDS.items():
        value = float(observation.metrics[field])
        breached = value >= threshold if direction == "high" else value <= threshold
        signals[signal] = (
            breached,
            "critical" if signal in {"oom_kill", "disk_capacity"} else "warning",
            {"value": value, "threshold": threshold, "field": field},
        )
    unhealthy = sorted(
        name
        for name, status in observation.service_health.items()
        if status != "active"
    )
    signals["service_health"] = (
        bool(unhealthy),
        "critical",
        {"unhealthy_services": unhealthy},
    )
    for signal, (breached, severity, evidence) in signals.items():
        _advance(
            db,
            observation.machine,
            signal,
            breached,
            severity,
            evidence,
            observation.observed_at,
        )


def evaluate_staleness(db: Session, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    machines = set(db.scalars(select(MachineObservation.machine).distinct()).all())
    for machine in machines:
        latest = db.scalar(
            select(MachineObservation)
            .where(MachineObservation.machine == machine)
            .order_by(MachineObservation.observed_at.desc())
            .limit(1)
        )
        stale = latest is None or now - latest.observed_at > STALE_AFTER
        _advance(
            db,
            machine,
            "availability",
            stale,
            "critical",
            {
                "last_observed_at": latest.observed_at.isoformat() if latest else None,
                "stale_after_seconds": int(STALE_AFTER.total_seconds()),
            },
            now,
        )
    db.commit()


def _advance(
    db: Session,
    machine: str,
    signal: str,
    breached: bool,
    severity: str,
    evidence: dict,
    now: datetime,
) -> None:
    incident = db.scalar(
        select(FleetIncident)
        .where(FleetIncident.machine == machine, FleetIncident.signal == signal)
        .order_by(FleetIncident.generation.desc())
        .limit(1)
    )
    active = incident is not None and incident.state not in {"recovered"}
    if not active and not breached:
        return
    if not active:
        incident = FleetIncident(
            machine=machine,
            signal=signal,
            state="pending",
            severity=severity,
            generation=(incident.generation + 1 if incident else 1),
            consecutive_breaches=0,
            consecutive_healthy=0,
            summary=f"{machine}: {signal.replace('_', ' ')}",
            evidence=evidence,
            opened_at=now,
            updated_at=now,
        )
        db.add(incident)
        db.flush()
        _event(db, incident, None, "pending", "detector", evidence)
    incident.evidence = evidence
    incident.updated_at = now
    if breached:
        incident.consecutive_breaches += 1
        incident.consecutive_healthy = 0
        if (
            incident.state == "silenced"
            and incident.silenced_until is not None
            and incident.silenced_until <= now
        ):
            _transition(db, incident, severity, "detector", evidence)
            _notify(db, incident, severity)
        if (
            incident.state == "pending"
            and incident.consecutive_breaches >= BREACH_SAMPLES
        ):
            _transition(db, incident, severity, "detector", evidence)
            _notify(db, incident, severity)
    else:
        incident.consecutive_healthy += 1
        incident.consecutive_breaches = 0
        if incident.state == "pending":
            _transition(db, incident, "recovered", "detector", evidence)
            incident.recovered_at = now
        elif (
            incident.state in {"warning", "critical", "acknowledged", "silenced"}
            and incident.consecutive_healthy >= RECOVERY_SAMPLES
        ):
            _transition(db, incident, "recovered", "detector", evidence)
            incident.recovered_at = now
            _notify(db, incident, "recovered")


def transition_incident(
    db: Session, incident: FleetIncident, action: IncidentAction, actor: str
) -> FleetIncident:
    now = datetime.now(UTC)
    if incident.state == "recovered":
        raise ValueError("Recovered incidents cannot be changed.")
    state = "acknowledged" if action.action == "acknowledge" else "silenced"
    _transition(db, incident, state, actor, {"reason": action.reason})
    if state == "acknowledged":
        incident.acknowledged_at = now
    else:
        incident.silenced_until = now + timedelta(seconds=action.silence_seconds or 0)
    db.commit()
    db.refresh(incident)
    return incident


def _transition(
    db: Session, incident: FleetIncident, state: str, actor: str, detail: dict
) -> None:
    prior = incident.state
    incident.state = state
    incident.updated_at = datetime.now(UTC)
    _event(db, incident, prior, state, actor, detail)


def _event(
    db: Session,
    incident: FleetIncident,
    prior: str | None,
    state: str,
    actor: str,
    detail: dict,
) -> None:
    document = {
        "incident_id": str(incident.id),
        "generation": incident.generation,
        "prior": prior,
        "state": state,
        "actor": actor,
        "detail": detail,
    }
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    db.add(
        FleetIncidentEvent(
            incident_id=incident.id,
            event_type="state_changed",
            prior_state=prior,
            resulting_state=state,
            actor=actor,
            detail=detail,
            record_digest=digest,
        )
    )


def _notify(db: Session, incident: FleetIncident, state: str) -> None:
    _insert_once(
        db,
        FounderNotification(
            kind="fleet_incident",
            entity_id=incident.id,
            deduplication_key=f"fleet:{incident.id}:{incident.generation}:{state}",
            state="pending",
            payload={
                "incident_id": str(incident.id),
                "machine": incident.machine,
                "signal": incident.signal,
                "severity": state,
                "summary": incident.summary,
                "evidence": incident.evidence,
            },
        ),
    )
