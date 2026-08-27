from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.offline_rl import OfflineRLDatasetContract
from app.schemas.offline_rl import OfflineRLDatasetCreate, OfflineRLDatasetResponse
from app.services.offline_rl import OfflineRLConflict, register_dataset

router = APIRouter(
    prefix="/v1/research/offline-rl-datasets",
    tags=["research-offline-rl"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=OfflineRLDatasetResponse, status_code=201)
def create_dataset(
    payload: OfflineRLDatasetCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_dataset(db, payload)
        db.commit()
        db.refresh(record)
        return OfflineRLDatasetResponse.model_validate(record)
    except OfflineRLConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[OfflineRLDatasetResponse])
def list_datasets(db: Annotated[Session, Depends(get_db)]):
    return [
        OfflineRLDatasetResponse.model_validate(item)
        for item in db.scalars(
            select(OfflineRLDatasetContract).order_by(
                OfflineRLDatasetContract.registered_at.desc()
            )
        ).all()
    ]


@router.get("/{dataset_id}", response_model=OfflineRLDatasetResponse)
def get_dataset(dataset_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(OfflineRLDatasetContract, dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Offline-RL dataset not found.")
    return OfflineRLDatasetResponse.model_validate(record)
