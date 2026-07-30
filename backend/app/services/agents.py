from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_agent_token
from app.models import Agent, AgentCredential


ONLINE_THRESHOLD_SECONDS = 90
DEGRADED_THRESHOLD_SECONDS = 300


def calculate_presence(
    agent: Agent,
    now: datetime | None = None,
) -> str:
    if not agent.is_enabled:
        return "revoked"

    if agent.last_heartbeat_at is None:
        return "offline"

    current_time = now or datetime.now(UTC)
    elapsed = (
        current_time - agent.last_heartbeat_at
    ).total_seconds()

    if elapsed <= ONLINE_THRESHOLD_SECONDS:
        return "online"

    if elapsed <= DEGRADED_THRESHOLD_SECONDS:
        return "degraded"

    return "offline"


def serialize_agent(
    agent: Agent,
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": agent.id,
        "slug": agent.slug,
        "display_name": agent.display_name,
        "role": agent.role,
        "machine": agent.machine,
        "hermes_profile": agent.hermes_profile,
        "runtime": agent.runtime,
        "runtime_version": agent.runtime_version,
        "status": agent.status,
        "presence": calculate_presence(agent, now),
        "capabilities": agent.capabilities,
        "heartbeat_metadata": agent.heartbeat_metadata,
        "risk_ceiling": agent.risk_ceiling,
        "is_enabled": agent.is_enabled,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


def issue_agent_credential(
    db: Session,
    agent: Agent,
) -> tuple[AgentCredential, str]:
    generated = create_agent_token()

    credential = AgentCredential(
        agent_id=agent.id,
        token_prefix=generated.prefix,
        token_digest=generated.digest,
    )

    db.add(credential)
    db.flush()
    db.refresh(credential)

    return credential, generated.token


def revoke_active_credentials(
    db: Session,
    agent_id,
    now: datetime | None = None,
) -> int:
    revoked_at = now or datetime.now(UTC)

    credentials = db.scalars(
        select(AgentCredential).where(
            AgentCredential.agent_id == agent_id,
            AgentCredential.revoked_at.is_(None),
        )
    ).all()

    for credential in credentials:
        credential.revoked_at = revoked_at

    return len(credentials)
