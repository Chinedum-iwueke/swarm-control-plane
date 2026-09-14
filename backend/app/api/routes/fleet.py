from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent
from app.models.fleet import FleetIncident, FleetIncidentEvent, MachineObservation
from app.schemas.fleet import (
    FleetIncidentResponse,
    IncidentAction,
    MachineObservationCreate,
    MachineObservationResponse,
)
from app.services.agents import calculate_presence
from app.services.fleet import (
    evaluate_staleness,
    record_observation,
    resolve_machine_presence,
    transition_incident,
)

agent_router = APIRouter(prefix="/v1/agent/fleet", tags=["fleet"])
router = APIRouter(
    prefix="/v1/fleet", tags=["fleet"], dependencies=[Depends(require_orchestrator)]
)


@agent_router.post("/observations", response_model=MachineObservationResponse)
def create_observation(
    payload: MachineObservationCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    if payload.machine != agent.machine:
        raise HTTPException(
            status_code=403, detail="Observation machine does not match agent identity."
        )
    skew = abs((datetime.now(UTC) - payload.observed_at).total_seconds())
    if skew > 120:
        raise HTTPException(
            status_code=422, detail="Observation clock skew exceeds 120 seconds."
        )
    return record_observation(db, agent.id, payload)


@router.get("/health")
def fleet_health(db: Annotated[Session, Depends(get_db)]):
    now = datetime.now(UTC)
    evaluate_staleness(db, now)
    machines = []
    agents = list(db.scalars(select(Agent)).all())
    names = set(db.scalars(select(MachineObservation.machine).distinct()).all())
    names.update(agent.machine for agent in agents)
    for name in sorted(names):
        latest = db.scalar(
            select(MachineObservation)
            .where(MachineObservation.machine == name)
            .order_by(MachineObservation.observed_at.desc())
            .limit(1)
        )
        incidents = list(
            db.scalars(
                select(FleetIncident)
                .where(
                    FleetIncident.machine == name, FleetIncident.state != "recovered"
                )
                .order_by(FleetIncident.updated_at.desc())
            ).all()
        )
        machine_agents = [agent for agent in agents if agent.machine == name]
        agent_presences = [calculate_presence(agent, now) for agent in machine_agents]
        presence, telemetry_status = resolve_machine_presence(
            latest.observed_at if latest is not None else None,
            agent_presences,
            now,
        )
        machines.append(
            {
                "machine": name,
                "presence": presence,
                "telemetry_status": telemetry_status,
                "registered_agents": len(machine_agents),
                "online_agents": agent_presences.count("online"),
                "status": "critical"
                if any(i.state == "critical" for i in incidents)
                else "warning"
                if incidents
                else "healthy",
                "last_observed_at": latest.observed_at if latest else None,
                "metrics": latest.metrics if latest else {},
                "services": latest.service_health if latest else {},
                "incidents": [
                    FleetIncidentResponse.model_validate(i).model_dump(mode="json")
                    for i in incidents
                ],
            }
        )
    return {"generated_at": datetime.now(UTC), "machines": machines}


@router.get("/incidents", response_model=list[FleetIncidentResponse])
def incidents(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    evaluate_staleness(db)
    return list(
        db.scalars(
            select(FleetIncident).order_by(FleetIncident.updated_at.desc()).limit(limit)
        ).all()
    )


@router.get("/incidents/{incident_id}/events")
def incident_events(incident_id: UUID, db: Annotated[Session, Depends(get_db)]):
    values = list(
        db.scalars(
            select(FleetIncidentEvent)
            .where(FleetIncidentEvent.incident_id == incident_id)
            .order_by(FleetIncidentEvent.id)
        ).all()
    )
    return [
        {
            "id": value.id,
            "incident_id": value.incident_id,
            "event_type": value.event_type,
            "prior_state": value.prior_state,
            "resulting_state": value.resulting_state,
            "actor": value.actor,
            "detail": value.detail,
            "record_digest": value.record_digest,
            "created_at": value.created_at,
        }
        for value in values
    ]


@router.post("/incidents/{incident_id}", response_model=FleetIncidentResponse)
def act_on_incident(
    incident_id: UUID, payload: IncidentAction, db: Annotated[Session, Depends(get_db)]
):
    incident = db.get(FleetIncident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Fleet incident not found.")
    try:
        return transition_incident(db, incident, payload, "founder-operator")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
