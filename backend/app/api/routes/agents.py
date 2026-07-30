from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import Agent
from app.schemas import (
    AgentCreate,
    AgentRegistrationResponse,
    AgentResponse,
    AgentRevocationResponse,
    CredentialSecretResponse,
)
from app.services.agents import (
    issue_agent_credential,
    revoke_active_credentials,
    serialize_agent,
)


router = APIRouter(
    prefix="/v1/agents",
    tags=["agents"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_agent(
    payload: AgentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> AgentRegistrationResponse:
    existing = db.scalar(
        select(Agent).where(Agent.slug == payload.slug)
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this slug already exists.",
        )

    agent = Agent(
        slug=payload.slug,
        display_name=payload.display_name,
        role=payload.role,
        machine=payload.machine,
        hermes_profile=payload.hermes_profile,
        status="offline",
        capabilities=payload.capabilities,
        risk_ceiling=payload.risk_ceiling,
        heartbeat_metadata={},
        is_enabled=True,
    )

    db.add(agent)

    try:
        db.flush()
        credential, raw_token = issue_agent_credential(db, agent)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent registration conflicted with existing data.",
        ) from exc

    db.refresh(agent)
    db.refresh(credential)

    return AgentRegistrationResponse(
        agent=AgentResponse.model_validate(
            serialize_agent(agent)
        ),
        credential=CredentialSecretResponse(
            token=raw_token,
            token_prefix=credential.token_prefix,
            created_at=credential.created_at,
        ),
    )


@router.get(
    "",
    response_model=list[AgentResponse],
)
def list_agents(
    db: Annotated[Session, Depends(get_db)],
) -> list[AgentResponse]:
    agents = db.scalars(
        select(Agent).order_by(Agent.created_at.asc())
    ).all()

    now = datetime.now(UTC)

    return [
        AgentResponse.model_validate(
            serialize_agent(agent, now)
        )
        for agent in agents
    ]


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
)
def get_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AgentResponse:
    agent = db.get(Agent, agent_id)

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    return AgentResponse.model_validate(
        serialize_agent(agent)
    )


@router.post(
    "/{agent_id}/credentials/rotate",
    response_model=AgentRegistrationResponse,
)
def rotate_agent_credential(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AgentRegistrationResponse:
    agent = db.get(Agent, agent_id)

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    if not agent.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot rotate credentials for a disabled agent.",
        )

    now = datetime.now(UTC)
    revoke_active_credentials(db, agent.id, now)

    credential, raw_token = issue_agent_credential(
        db,
        agent,
    )

    db.commit()
    db.refresh(agent)
    db.refresh(credential)

    return AgentRegistrationResponse(
        agent=AgentResponse.model_validate(
            serialize_agent(agent, now)
        ),
        credential=CredentialSecretResponse(
            token=raw_token,
            token_prefix=credential.token_prefix,
            created_at=credential.created_at,
        ),
    )


@router.post(
    "/{agent_id}/revoke",
    response_model=AgentRevocationResponse,
)
def revoke_agent(
    agent_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AgentRevocationResponse:
    agent = db.get(Agent, agent_id)

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    now = datetime.now(UTC)
    revoked_credentials = revoke_active_credentials(
        db,
        agent.id,
        now,
    )

    agent.is_enabled = False
    agent.status = "revoked"

    db.commit()

    return AgentRevocationResponse(
        agent_id=agent.id,
        revoked_credentials=revoked_credentials,
        status="revoked",
    )
