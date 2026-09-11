from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.venue_identity import VenueIdentityRegistry
from app.schemas.venue_identity import VenueIdentityCreate, VenueIdentityResponse
from app.services.venue_identity import (
    VenueIdentityConflict,
    register_venue_identity,
)

router = APIRouter(
    prefix="/v1/research/venue-identities",
    tags=["research-venue-identities"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=VenueIdentityResponse, status_code=201)
def create_venue_identity(
    payload: VenueIdentityCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_venue_identity(db, payload)
        db.commit()
        db.refresh(record)
        return VenueIdentityResponse.model_validate(record)
    except VenueIdentityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[VenueIdentityResponse])
def list_venue_identities(db: Annotated[Session, Depends(get_db)]):
    return [
        VenueIdentityResponse.model_validate(item)
        for item in db.scalars(
            select(VenueIdentityRegistry).order_by(
                VenueIdentityRegistry.registered_at
            )
        ).all()
    ]


@router.get("/{identity_id}", response_model=VenueIdentityResponse)
def get_venue_identity(
    identity_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(VenueIdentityRegistry, identity_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Venue identity not found.")
    return VenueIdentityResponse.model_validate(record)
