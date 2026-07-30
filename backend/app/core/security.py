from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Agent, AgentCredential


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class GeneratedAgentCredential:
    token: str
    prefix: str
    digest: str


def create_agent_token() -> GeneratedAgentCredential:
    prefix = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    token = f"swarm_ag_{prefix}_{secret}"

    return GeneratedAgentCredential(
        token=token,
        prefix=prefix,
        digest=digest_agent_token(token),
    )


def digest_agent_token(token: str) -> str:
    settings = get_settings()

    return hmac.new(
        settings.agent_token_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def extract_agent_token_prefix(token: str) -> str | None:
    parts = token.split("_", 3)

    if len(parts) != 4:
        return None

    namespace, credential_type, prefix, secret = parts

    if namespace != "swarm" or credential_type != "ag":
        return None

    if not prefix or not secret:
        return None

    return prefix


def require_orchestrator(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> None:
    settings = get_settings()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative credential required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hmac.compare_digest(
        credentials.credentials,
        settings.orchestrator_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_agent(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent credential required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    prefix = extract_agent_token_prefix(token)

    if prefix is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credential = db.scalar(
        select(AgentCredential).where(
            AgentCredential.token_prefix == prefix
        )
    )

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(UTC)

    if credential.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent credential has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if (
        credential.expires_at is not None
        and credential.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent credential has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied_digest = digest_agent_token(token)

    if not hmac.compare_digest(
        supplied_digest,
        credential.token_digest,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    agent = db.get(Agent, credential.agent_id)

    if agent is None or not agent.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is disabled.",
        )

    credential.last_used_at = now
    db.commit()

    return agent


@dataclass(frozen=True)
class GeneratedTaskLeaseToken:
    token: str
    prefix: str
    digest: str


def create_task_lease_token() -> GeneratedTaskLeaseToken:
    prefix = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    token = f"swarm_lt_{prefix}_{secret}"

    return GeneratedTaskLeaseToken(
        token=token,
        prefix=prefix,
        digest=digest_task_lease_token(token),
    )


def digest_task_lease_token(token: str) -> str:
    settings = get_settings()

    domain_separated_value = f"task-lease:{token}"

    return hmac.new(
        settings.agent_token_secret.encode("utf-8"),
        domain_separated_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def extract_task_lease_token_prefix(token: str) -> str | None:
    parts = token.split("_", 3)

    if len(parts) != 4:
        return None

    namespace, credential_type, prefix, secret = parts

    if namespace != "swarm" or credential_type != "lt":
        return None

    if not prefix or not secret:
        return None

    return prefix
