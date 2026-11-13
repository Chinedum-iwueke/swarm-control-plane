from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, FounderNotification, Task
from app.models.provider_capacity import (
    ProviderCapacityCircuit,
    ProviderCapacityEvent,
)
from app.services.founder_notifications import _insert_once

PROBE_LEASE_SECONDS = 300


def _matches(circuit: ProviderCapacityCircuit, agent: Agent) -> bool:
    required = set(circuit.blocked_capabilities or [])
    return bool(required) and required.issubset(set(agent.capabilities or []))


def claim_due_probes_or_block(
    db: Session, agent: Agent, *, claim: bool = True
) -> tuple[list[str], list[str]]:
    now = datetime.now(UTC)
    circuits = list(
        db.scalars(
            select(ProviderCapacityCircuit)
            .where(ProviderCapacityCircuit.state.in_(["open", "half_open"]))
            .order_by(ProviderCapacityCircuit.provider)
            .with_for_update()
        ).all()
    )
    relevant = [item for item in circuits if _matches(item, agent)]
    if not relevant:
        return [], []

    blocked: list[str] = []
    for circuit in relevant:
        probe_is_live = (
            circuit.state == "half_open"
            and circuit.probe_expires_at is not None
            and circuit.probe_expires_at > now
        )
        if probe_is_live or (circuit.next_probe_at and circuit.next_probe_at > now):
            blocked.append(
                f"{circuit.provider} provider capacity circuit is {circuit.state}; "
                f"next probe at {circuit.next_probe_at.isoformat() if circuit.next_probe_at else 'pending'}"
            )
    if blocked:
        return [], blocked

    if not claim:
        return [], []

    providers: list[str] = []
    for circuit in relevant:
        circuit.state = "half_open"
        circuit.probe_agent_id = agent.id
        circuit.probe_expires_at = now + timedelta(seconds=PROBE_LEASE_SECONDS)
        circuit.next_probe_at = circuit.probe_expires_at
        circuit.updated_at = now
        db.add(
            ProviderCapacityEvent(
                circuit_id=circuit.id,
                event_type="probe_claimed",
                actor=agent.slug,
                payload={"probe_expires_at": circuit.probe_expires_at.isoformat()},
            )
        )
        providers.append(circuit.provider)
    db.flush()
    return providers, []


def open_circuit(
    db: Session,
    *,
    provider: str,
    task: Task,
    agent: Agent,
    failure_summary: str,
    retry_after_seconds: int,
) -> tuple[ProviderCapacityCircuit, bool]:
    now = datetime.now(UTC)
    circuit = db.scalar(
        select(ProviderCapacityCircuit)
        .where(ProviderCapacityCircuit.provider == provider)
        .with_for_update()
    )
    new_incident = circuit is None or circuit.state == "closed"
    if circuit is None:
        circuit = ProviderCapacityCircuit(
            provider=provider,
            state="open",
            generation=1,
            consecutive_failures=1,
        )
        db.add(circuit)
        db.flush()
    else:
        if new_incident:
            circuit.generation += 1
            circuit.consecutive_failures = 1
        else:
            circuit.consecutive_failures += 1
        circuit.state = "open"

    cooldown = min(
        21_600,
        retry_after_seconds * (2 ** max(0, circuit.consecutive_failures - 1)),
    )
    circuit.blocked_capabilities = sorted(
        set(task.required_capabilities or agent.capabilities or [])
    )
    circuit.failure_summary = failure_summary
    circuit.source_task_id = task.id
    circuit.probe_agent_id = None
    circuit.probe_expires_at = None
    circuit.opened_at = circuit.opened_at if not new_incident else now
    circuit.next_probe_at = now + timedelta(seconds=cooldown)
    circuit.recovered_at = None
    circuit.updated_at = now
    db.flush()
    db.add(
        ProviderCapacityEvent(
            circuit_id=circuit.id,
            event_type="circuit_opened" if new_incident else "probe_exhausted",
            actor=agent.slug,
            payload={
                "task_id": str(task.id),
                "task_number": task.task_number,
                "next_probe_at": circuit.next_probe_at.isoformat(),
                "consecutive_failures": circuit.consecutive_failures,
            },
        )
    )
    key = f"provider-capacity:{circuit.id}:{circuit.generation}"
    existing_notification = db.scalar(
        select(FounderNotification).where(
            FounderNotification.deduplication_key == key
        )
    )
    _insert_once(
        db,
        FounderNotification(
            kind="provider_capacity_exhausted",
            entity_id=circuit.id,
            deduplication_key=key,
            state="pending",
            payload={
                "circuit_id": str(circuit.id),
                "provider": provider,
                "generation": circuit.generation,
                "failure_summary": failure_summary,
                "next_probe_at": circuit.next_probe_at.isoformat(),
                "task_number": task.task_number,
            },
        ),
    )
    db.flush()
    return circuit, existing_notification is None


def report_probe(
    db: Session,
    *,
    provider: str,
    agent: Agent,
    healthy: bool,
    failure_summary: str | None,
    retry_after_seconds: int,
) -> ProviderCapacityCircuit:
    now = datetime.now(UTC)
    circuit = db.scalar(
        select(ProviderCapacityCircuit)
        .where(ProviderCapacityCircuit.provider == provider)
        .with_for_update()
    )
    if circuit is None:
        raise HTTPException(status_code=404, detail="Provider circuit not found.")
    if circuit.state != "half_open" or circuit.probe_agent_id != agent.id:
        raise HTTPException(status_code=409, detail="Provider probe is not assigned.")
    if healthy:
        circuit.state = "closed"
        circuit.consecutive_failures = 0
        circuit.failure_summary = None
        circuit.probe_agent_id = None
        circuit.probe_expires_at = None
        circuit.next_probe_at = None
        circuit.recovered_at = now
        event_type = "circuit_closed"
        notifications = db.scalars(
            select(FounderNotification).where(
                FounderNotification.entity_id == circuit.id,
                FounderNotification.kind == "provider_capacity_exhausted",
                FounderNotification.state.in_(["pending", "waiting"]),
            )
        ).all()
        for notification in notifications:
            notification.state = "superseded"
            notification.superseded_at = now
            notification.updated_at = now
    else:
        circuit.state = "open"
        circuit.consecutive_failures += 1
        circuit.failure_summary = failure_summary or circuit.failure_summary
        circuit.probe_agent_id = None
        circuit.probe_expires_at = None
        cooldown = min(
            21_600,
            retry_after_seconds * (2 ** max(0, circuit.consecutive_failures - 1)),
        )
        circuit.next_probe_at = now + timedelta(seconds=cooldown)
        event_type = "probe_exhausted"
    circuit.updated_at = now
    db.add(
        ProviderCapacityEvent(
            circuit_id=circuit.id,
            event_type=event_type,
            actor=agent.slug,
            payload={
                "healthy": healthy,
                "next_probe_at": (
                    circuit.next_probe_at.isoformat() if circuit.next_probe_at else None
                ),
            },
        )
    )
    db.flush()
    return circuit
