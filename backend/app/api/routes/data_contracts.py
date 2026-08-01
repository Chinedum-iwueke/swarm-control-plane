from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.data_contract import ResearchDatasetBuild, ResearchDatasetManifest
from app.schemas.data_contract import (
    DatasetBuildCreate,
    DatasetBuildResponse,
    DatasetManifestCreate,
    DatasetManifestResponse,
)
from app.services.data_contracts import (
    DataContractConflict,
    register_build,
    register_manifest,
)

router = APIRouter(
    prefix="/v1/research/data-contracts",
    tags=["research-data-contracts"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/manifests", response_model=DatasetManifestResponse, status_code=201)
def create_manifest(
    payload: DatasetManifestCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_manifest(db, payload)
        db.commit()
        db.refresh(record)
        return DatasetManifestResponse.model_validate(record)
    except DataContractConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/manifests", response_model=list[DatasetManifestResponse])
def list_manifests(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    records = db.scalars(
        select(ResearchDatasetManifest)
        .order_by(ResearchDatasetManifest.registered_at.desc())
        .limit(limit)
    ).all()
    return [DatasetManifestResponse.model_validate(record) for record in records]


@router.get("/manifests/{manifest_id}", response_model=DatasetManifestResponse)
def get_manifest(manifest_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(ResearchDatasetManifest, manifest_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset manifest not found.")
    return DatasetManifestResponse.model_validate(record)


@router.post("/builds", response_model=DatasetBuildResponse, status_code=201)
def create_build(payload: DatasetBuildCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_build(db, payload)
        db.commit()
        db.refresh(record)
        return DatasetBuildResponse.model_validate(record)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataContractConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/builds", response_model=list[DatasetBuildResponse])
def list_builds(
    db: Annotated[Session, Depends(get_db)],
    manifest_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    statement = select(ResearchDatasetBuild)
    if manifest_id is not None:
        statement = statement.where(ResearchDatasetBuild.manifest_id == manifest_id)
    records = db.scalars(
        statement.order_by(ResearchDatasetBuild.registered_at.desc()).limit(limit)
    ).all()
    return [DatasetBuildResponse.model_validate(record) for record in records]
