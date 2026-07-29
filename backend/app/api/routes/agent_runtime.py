from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_agent
from app.db.session import get_db
from app.models import Agent
from app.schemas import (
    AgentHeartbeat,
    AgentHeartbeatResponse,
    AgentResponse,
)
from app.services.agents import serialize_agent


router = APIRouter(
    prefix="/v1/agent",
    tags=["agent-runtime"],
)


@router.get(
    "/me",
    response_model=AgentResponse,
)
def get_agent_identity(
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> AgentResponse:
    return AgentResponse.model_validate(
        serialize_agent(agent)
    )


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
)
def receive_heartbeat(
    payload: AgentHeartbeat,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentHeartbeatResponse:
    now = datetime.now(UTC)

    agent.status = payload.status
    agent.runtime = payload.runtime
    agent.runtime_version = payload.runtime_version
    agent.heartbeat_metadata = payload.metadata
    agent.last_heartbeat_at = now

    if payload.capabilities is not None:
        agent.capabilities = payload.capabilities

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return AgentHeartbeatResponse(
        agent_id=agent.id,
        status=agent.status,
        presence="online",
        received_at=now,
    )
