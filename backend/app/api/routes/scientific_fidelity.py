from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.scientific_fidelity import (
    ScientificFidelityManifest,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    FidelityManifestResponse,
    ScientificRepresentationCreate,
    ScientificRepresentationResponse,
)
from app.services.scientific_fidelity import (
    ScientificFidelityConflict,
    publish_manifest,
    register_representation,
)

router = APIRouter(
    prefix="/v1/research/scientific-fidelity",
    tags=["research-scientific-fidelity"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/representations", response_model=ScientificRepresentationResponse, status_code=201
)
def create_representation(
    payload: ScientificRepresentationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_representation(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/representations", response_model=list[ScientificRepresentationResponse])
def list_representations(
    db: Annotated[Session, Depends(get_db)], status: str | None = None
):
    query = select(ScientificRepresentation).order_by(
        ScientificRepresentation.created_at
    )
    if status:
        query = query.where(ScientificRepresentation.status == status)
    return list(db.scalars(query).all())


@router.get(
    "/representations/{representation_id}",
    response_model=ScientificRepresentationResponse,
)
def get_representation(
    representation_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ScientificRepresentation, representation_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Scientific representation not found."
        )
    return record


@router.post("/manifests", response_model=FidelityManifestResponse, status_code=201)
def create_manifest(
    payload: FidelityManifestCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = publish_manifest(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/manifests", response_model=list[FidelityManifestResponse])
def list_manifests(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(ScientificFidelityManifest).order_by(
                ScientificFidelityManifest.created_at.desc()
            )
        ).all()
    )
