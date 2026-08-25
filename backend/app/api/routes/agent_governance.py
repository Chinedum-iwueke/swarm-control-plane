from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import AgentCapabilityGrant, AgentCharter
from app.schemas.agent_governance import (
    AgentCapabilityGrantCreate,
    AgentCapabilityGrantResponse,
    AgentCharterActivation,
    AgentCharterCreate,
    AgentCharterResponse,
    AgentGrantRevocation,
    EffectiveAuthorityRequest,
    EffectiveAuthorityResponse,
)
from app.services.agent_governance import (
    activate_charter,
    create_charter,
    create_grant,
    resolve,
    revoke_grant,
)

router = APIRouter(prefix="/v1/agent-governance", tags=["agent-governance"], dependencies=[Depends(require_orchestrator)])

@router.post("/charters", response_model=AgentCharterResponse, status_code=201)
def register(payload: AgentCharterCreate, db: Annotated[Session, Depends(get_db)]):
    try: return create_charter(db, payload)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "Charter version or digest already exists.") from exc

@router.post("/charters/{charter_id}/activate", response_model=AgentCharterResponse)
def activate(charter_id: UUID, payload: AgentCharterActivation, db: Annotated[Session, Depends(get_db)]):
    charter = db.get(AgentCharter, charter_id)
    if not charter: raise HTTPException(404, "Charter not found.")
    return activate_charter(db, charter, payload.activated_by)

@router.get("/charters", response_model=list[AgentCharterResponse])
def charters(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(select(AgentCharter).order_by(AgentCharter.created_at)).all()

@router.post("/grants", response_model=AgentCapabilityGrantResponse, status_code=201)
def grant(payload: AgentCapabilityGrantCreate, db: Annotated[Session, Depends(get_db)]):
    return create_grant(db, payload)

@router.post("/grants/{grant_id}/revoke", response_model=AgentCapabilityGrantResponse)
def revoke(grant_id: UUID, payload: AgentGrantRevocation, db: Annotated[Session, Depends(get_db)]):
    grant = db.get(AgentCapabilityGrant, grant_id)
    if not grant: raise HTTPException(404, "Grant not found.")
    return revoke_grant(db, grant, payload.revoked_by, payload.reason)

@router.get("/grants", response_model=list[AgentCapabilityGrantResponse])
def grants(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(
        select(AgentCapabilityGrant).order_by(AgentCapabilityGrant.created_at)
    ).all()

@router.post("/agents/{agent_id}/resolve", response_model=EffectiveAuthorityResponse)
def effective(agent_id: UUID, payload: EffectiveAuthorityRequest, db: Annotated[Session, Depends(get_db)]):
    return resolve(db, agent_id, payload)
