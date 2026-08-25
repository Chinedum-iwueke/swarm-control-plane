from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FounderNotification
from app.models.fleet import MachineObservation
from app.models.observability import (
    AlertRoutingEvent,
    RoutedServiceAlert,
    ServiceSLOState,
)
from app.models.platform import (
    ServiceCatalogActivation,
    ServiceCatalogReconciliation,
    ServiceCatalogSnapshot,
)
from app.schemas.observability import AlertAction
from app.services.founder_notifications import _insert_once

BREACH_SAMPLES = 3
RECOVERY_SAMPLES = 3
_SECRET = re.compile(r"(?i)(password|secret|token|authorization|api[_-]?key)")
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+\S+|(?:password|secret|token|api[_-]?key)\s*[=:]\s*\S+|swarm_(?:ag|lt)_\S+)"
)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def sanitized(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return "[TRUNCATED]"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return sanitized(value.value, depth=depth + 1)
    if isinstance(value, dict):
        return {
            str(key)[:100]: "[REDACTED]"
            if _SECRET.search(str(key))
            else sanitized(item, depth=depth + 1)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, list):
        return [sanitized(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", value[:500])
    return value


def _active_catalog(db: Session) -> ServiceCatalogSnapshot | None:
    activation = db.scalar(
        select(ServiceCatalogActivation).where(
            ServiceCatalogActivation.is_current.is_(True)
        )
    )
    return (
        db.get(ServiceCatalogSnapshot, activation.snapshot_id) if activation else None
    )


def _latest_reconciliation(db: Session) -> ServiceCatalogReconciliation | None:
    return db.scalar(
        select(ServiceCatalogReconciliation)
        .order_by(ServiceCatalogReconciliation.reconciled_at.desc())
        .limit(1)
    )


def evaluate_observability(db: Session, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    catalog = _active_catalog(db)
    if catalog is None:
        return {
            "generated_at": now,
            "catalog": None,
            "summary": {"unknown": 1},
            "services": [],
            "alerts": [],
        }
    reconciliation = _latest_reconciliation(db)
    observed = {
        item["service_key"]: item
        for item in (
            (reconciliation.observations or {}).get("items", [])
            if reconciliation
            else []
        )
    }
    latest_machine: dict[str, MachineObservation] = {}
    for machine in {
        m for entry in catalog.manifest["entries"] for m in entry["intended_machines"]
    }:
        item = db.scalar(
            select(MachineObservation)
            .where(MachineObservation.machine == machine)
            .order_by(MachineObservation.observed_at.desc())
            .limit(1)
        )
        if item is not None:
            latest_machine[machine] = item

    rows: list[dict[str, Any]] = []
    for entry in catalog.manifest["entries"][:500]:
        rows.extend(
            _service_rows(
                entry, observed.get(entry["service_key"]), latest_machine, now
            )
        )
    states = [_persist_state(db, row, now) for row in rows]
    for state in states:
        _route_state(db, state, now)
    db.commit()
    alerts = list(
        db.scalars(
            select(RoutedServiceAlert)
            .where(RoutedServiceAlert.state != "recovered")
            .order_by(RoutedServiceAlert.updated_at.desc())
        ).all()
    )
    summary: dict[str, int] = {}
    for state in states:
        summary[state.status] = summary.get(state.status, 0) + 1
    return {
        "generated_at": now,
        "catalog": {
            "version": catalog.catalog_version,
            "digest": catalog.manifest_digest,
        },
        "summary": summary,
        "services": [_state_doc(item) for item in states],
        "alerts": [_alert_doc(item) for item in alerts],
        "claim_boundary": "Current-window evidence; historical availability is not inferred from a single sample.",
    }


def _service_rows(
    entry: dict,
    observation: dict | None,
    machines: dict[str, MachineObservation],
    now: datetime,
) -> list[dict]:
    key, owner, slo = entry["service_key"], entry["owner"], entry["slo"]
    evidence = {"observation": observation, "machines": entry["intended_machines"]}
    rows: list[dict] = []
    if "availability_percent" in slo:
        status = (
            "missing"
            if observation is None
            else "healthy"
            if observation.get("status") == "healthy"
            else "breached"
        )
        rows.append(
            _row(
                key,
                owner,
                "availability",
                {
                    "target_percent": slo["availability_percent"],
                    "window": "current_evidence",
                },
                {
                    "observed_percent": None
                    if observation is None
                    else 100.0
                    if status == "healthy"
                    else 0.0,
                    "sample_count": 0 if observation is None else 1,
                },
                evidence,
                status,
            )
        )
    freshness = slo.get("heartbeat_seconds") or slo.get("sample_seconds")
    if freshness:
        samples = [machines.get(machine) for machine in entry["intended_machines"]]
        latest = max((item.observed_at for item in samples if item), default=None)
        age = (now - latest).total_seconds() if latest else None
        status = (
            "missing"
            if age is None
            else "healthy"
            if age <= freshness * 3
            else "breached"
        )
        rows.append(
            _row(
                key,
                owner,
                "telemetry_freshness",
                {"maximum_age_seconds": freshness * 3},
                {"age_seconds": age, "last_observed_at": latest},
                evidence,
                status,
            )
        )
    if "rpo_seconds" in slo:
        sample = next(
            (
                machines.get(machine)
                for machine in entry["intended_machines"]
                if machines.get(machine)
            ),
            None,
        )
        age = (
            (sample.metrics or {}).get("control_plane_backup_age_seconds")
            if sample
            else None
        )
        verified = (
            (sample.metrics or {}).get("control_plane_backup_verified")
            if sample
            else None
        )
        status = (
            "missing"
            if age is None or verified is None
            else "healthy"
            if verified and age <= slo["rpo_seconds"]
            else "breached"
        )
        rows.append(
            _row(
                key,
                owner,
                "recovery_point",
                {"maximum_age_seconds": slo["rpo_seconds"]},
                {"age_seconds": age, "integrity_verified": verified},
                evidence,
                status,
            )
        )
    if "rto_seconds" in slo:
        rows.append(
            _row(
                key,
                owner,
                "recovery_time",
                {"maximum_seconds": slo["rto_seconds"]},
                {"measured_seconds": None},
                {
                    "reason": "No current restore-drill measurement is attached to this service SLO."
                },
                "unknown",
            )
        )
    sample = next(
        (
            machines.get(machine)
            for machine in entry["intended_machines"]
            if machines.get(machine)
        ),
        None,
    )
    if sample:
        memory = float(sample.metrics.get("memory_available_percent", 0))
        disk = float(sample.metrics.get("disk_used_percent", 100))
        status = "breached" if memory < 10 or disk >= 90 else "healthy"
        rows.append(
            _row(
                key,
                owner,
                "capacity",
                {
                    "memory_available_minimum_percent": 10,
                    "disk_used_maximum_percent": 90,
                },
                {"memory_available_percent": memory, "disk_used_percent": disk},
                {"machine": sample.machine, "observed_at": sample.observed_at},
                status,
            )
        )
    return rows


def _row(
    service: str,
    owner: str,
    indicator: str,
    objective: dict,
    measurement: dict,
    evidence: dict,
    status: str,
) -> dict:
    return {
        "service_key": service,
        "owner": owner,
        "indicator": indicator,
        "objective": objective,
        "measurement": measurement,
        "evidence": sanitized(evidence),
        "status": status,
    }


def _persist_state(db: Session, row: dict, now: datetime) -> ServiceSLOState:
    state = db.scalar(
        select(ServiceSLOState).where(
            ServiceSLOState.service_key == row["service_key"],
            ServiceSLOState.indicator == row["indicator"],
        )
    )
    if state is None:
        state = ServiceSLOState(
            service_key=row["service_key"],
            indicator=row["indicator"],
            owner=row["owner"],
            status=row["status"],
            objective=row["objective"],
            measurement=row["measurement"],
            evidence=row["evidence"],
            evaluated_at=now,
            record_digest="0" * 64,
        )
        db.add(state)
        db.flush()
    state.owner, state.status, state.objective = (
        row["owner"],
        row["status"],
        row["objective"],
    )
    state.measurement, state.evidence, state.evaluated_at = (
        row["measurement"],
        row["evidence"],
        now,
    )
    if state.status in {"breached", "missing"}:
        state.consecutive_breaches += 1
        state.consecutive_healthy = 0
    elif state.status == "healthy":
        state.consecutive_healthy += 1
        state.consecutive_breaches = 0
    state.record_digest = digest(_state_doc(state))
    return state


def _route_state(db: Session, state: ServiceSLOState, now: datetime) -> None:
    alert = db.scalar(
        select(RoutedServiceAlert).where(
            RoutedServiceAlert.alert_key == f"slo:{state.service_key}:{state.indicator}"
        )
    )
    breached = state.status in {"breached", "missing"}
    if alert is None and state.consecutive_breaches < BREACH_SAMPLES:
        return
    if alert is None:
        alert = RoutedServiceAlert(
            alert_key=f"slo:{state.service_key}:{state.indicator}",
            service_key=state.service_key,
            indicator=state.indicator,
            owner=state.owner,
            severity="critical" if state.status == "missing" else "warning",
            state="firing",
            generation=1,
            summary=f"{state.service_key}: {state.indicator.replace('_', ' ')}",
            evidence=state.evidence,
            route="founder-outbox",
            opened_at=now,
            updated_at=now,
            record_digest="0" * 64,
        )
        db.add(alert)
        db.flush()
        _alert_event(db, alert, "fired", "slo-evaluator", state.evidence)
        _notify(db, alert, "firing")
    elif breached:
        alert.evidence, alert.updated_at = state.evidence, now
        if alert.state == "recovered" and state.consecutive_breaches >= BREACH_SAMPLES:
            alert.generation += 1
            alert.state = "firing"
            alert.severity = "critical" if state.status == "missing" else "warning"
            alert.opened_at = now
            alert.recovered_at = None
            _alert_event(db, alert, "reopened", "slo-evaluator", state.evidence)
            _notify(db, alert, "firing")
        elif (
            alert.state == "silenced"
            and alert.silenced_until
            and alert.silenced_until <= now
        ):
            alert.state = "firing"
            _alert_event(db, alert, "silence_expired", "slo-evaluator", {})
    elif (
        state.status == "healthy"
        and alert.state != "recovered"
        and state.consecutive_healthy >= RECOVERY_SAMPLES
    ):
        alert.state, alert.recovered_at, alert.updated_at = "recovered", now, now
        _alert_event(db, alert, "recovered", "slo-evaluator", state.measurement)
        _notify(db, alert, "recovered")
    alert.record_digest = digest(_alert_doc(alert))


def transition_alert(
    db: Session,
    alert: RoutedServiceAlert,
    action: AlertAction,
    now: datetime | None = None,
) -> RoutedServiceAlert:
    now = now or datetime.now(UTC)
    if alert.state == "recovered":
        raise ValueError("Recovered alerts cannot be changed.")
    if action.action == "acknowledge":
        alert.state, alert.acknowledged_at = "acknowledged", now
    elif action.action == "silence":
        alert.state, alert.silenced_until = (
            "silenced",
            now + timedelta(seconds=action.silence_seconds or 0),
        )
    else:
        alert.state, alert.silenced_until = "firing", None
    alert.updated_at = now
    _alert_event(
        db,
        alert,
        action.action,
        "founder-operator",
        {"reason": action.reason, "silence_seconds": action.silence_seconds},
    )
    alert.record_digest = digest(_alert_doc(alert))
    db.commit()
    db.refresh(alert)
    return alert


def _alert_event(
    db: Session, alert: RoutedServiceAlert, event: str, actor: str, detail: dict
) -> None:
    sequence = (
        db.scalar(
            select(func.max(AlertRoutingEvent.sequence)).where(
                AlertRoutingEvent.alert_id == alert.id
            )
        )
        or 0
    ) + 1
    body = {
        "alert_id": str(alert.id),
        "sequence": sequence,
        "event": event,
        "actor": actor,
        "detail": sanitized(detail),
    }
    db.add(
        AlertRoutingEvent(
            alert_id=alert.id,
            sequence=sequence,
            event_type=event,
            actor=actor,
            detail=body["detail"],
            record_digest=digest(body),
        )
    )


def _notify(db: Session, alert: RoutedServiceAlert, state: str) -> None:
    _insert_once(
        db,
        FounderNotification(
            kind="service_slo_alert",
            entity_id=alert.id,
            deduplication_key=f"slo:{alert.id}:{alert.generation}:{state}",
            state="pending",
            payload={
                "alert_id": str(alert.id),
                "service_key": alert.service_key,
                "indicator": alert.indicator,
                "severity": alert.severity,
                "state": state,
                "summary": alert.summary,
                "owner": alert.owner,
                "evidence": sanitized(alert.evidence),
            },
        ),
    )


def _state_doc(state: ServiceSLOState) -> dict:
    return {
        "id": str(state.id),
        "service_key": state.service_key,
        "indicator": state.indicator,
        "owner": state.owner,
        "status": state.status,
        "objective": state.objective,
        "measurement": state.measurement,
        "evidence": state.evidence,
        "consecutive_breaches": state.consecutive_breaches,
        "consecutive_healthy": state.consecutive_healthy,
        "evaluated_at": state.evaluated_at,
    }


def _alert_doc(alert: RoutedServiceAlert) -> dict:
    return {
        "id": str(alert.id),
        "service_key": alert.service_key,
        "indicator": alert.indicator,
        "owner": alert.owner,
        "severity": alert.severity,
        "state": alert.state,
        "generation": alert.generation,
        "summary": alert.summary,
        "evidence": alert.evidence,
        "route": alert.route,
        "acknowledged_at": alert.acknowledged_at,
        "silenced_until": alert.silenced_until,
        "recovered_at": alert.recovered_at,
        "opened_at": alert.opened_at,
        "updated_at": alert.updated_at,
    }
