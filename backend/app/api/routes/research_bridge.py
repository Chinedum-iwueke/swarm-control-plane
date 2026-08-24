from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.research_bridge import GovernedResearchAdvance, GovernedResearchBridgeCreate, GovernedResearchBridgeResponse
from app.services.research_bridge import advance_bridge, create_bridge, get_bridge


router = APIRouter(
    prefix="/v1/research/governed-bridges",
    tags=["governed-research"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=GovernedResearchBridgeResponse, status_code=201)
def create(payload: GovernedResearchBridgeCreate, db: Annotated[Session, Depends(get_db)]):
    return GovernedResearchBridgeResponse.model_validate(create_bridge(db, payload.proposal), from_attributes=True)


@router.get("/{bridge_id}", response_model=GovernedResearchBridgeResponse)
def read(bridge_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return GovernedResearchBridgeResponse.model_validate(get_bridge(db, bridge_id), from_attributes=True)


@router.post("/{bridge_id}/advance", response_model=GovernedResearchBridgeResponse)
def advance(bridge_id: UUID, payload: GovernedResearchAdvance, db: Annotated[Session, Depends(get_db)]):
    return GovernedResearchBridgeResponse.model_validate(advance_bridge(db, bridge_id, payload), from_attributes=True)
