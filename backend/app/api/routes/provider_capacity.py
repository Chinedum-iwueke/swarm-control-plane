from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent
from app.models.provider_capacity import ProviderCapacityCircuit
from app.schemas.provider_capacity import (
    ProviderCapacityCircuitResponse,
    ProviderProbeReport,
    ProviderProbeResponse,
)
from app.services.provider_capacity import report_probe

router = APIRouter(prefix="/v1/provider-capacity", tags=["provider-capacity"])


@router.get(
    "/circuits",
    response_model=list[ProviderCapacityCircuitResponse],
    dependencies=[Depends(require_orchestrator)],
)
def list_circuits(
    db: Annotated[Session, Depends(get_db)],
) -> list[ProviderCapacityCircuitResponse]:
    values = db.scalars(
        select(ProviderCapacityCircuit).order_by(ProviderCapacityCircuit.provider)
    ).all()
    return [ProviderCapacityCircuitResponse.model_validate(item) for item in values]


agent_router = APIRouter(
    prefix="/v1/agent/provider-capacity", tags=["agent-provider-capacity"]
)


@agent_router.post(
    "/{provider}/probe",
    response_model=ProviderProbeResponse,
)
def submit_probe(
    provider: str,
    payload: ProviderProbeReport,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderProbeResponse:
    if not provider or len(provider) > 50:
        raise HTTPException(status_code=422, detail="Invalid provider key.")
    circuit = report_probe(
        db,
        provider=provider,
        agent=agent,
        healthy=payload.outcome == "healthy",
        failure_summary=payload.failure_summary,
        retry_after_seconds=payload.retry_after_seconds,
    )
    db.commit()
    db.refresh(circuit)
    return ProviderProbeResponse(
        circuit=ProviderCapacityCircuitResponse.model_validate(circuit)
    )
