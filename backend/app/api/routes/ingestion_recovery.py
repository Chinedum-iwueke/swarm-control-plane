from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.ingestion import _pipeline, _store
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.ingestion import (
    IngestionRecoveryBatchResponse,
    IngestionRecoveryCreate,
    IngestionRecoveryResponse,
)
from app.services.ingestion_recovery import process_next_recovery, queue_recoveries

router = APIRouter(
    prefix="/v1/research/ingestion/recoveries",
    tags=["scientific-ingestion-recovery"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=IngestionRecoveryBatchResponse, status_code=202)
def create_recovery_batch(
    payload: IngestionRecoveryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    queued, existing, ids = queue_recoveries(db, payload)
    return IngestionRecoveryBatchResponse(
        queued=queued, existing=existing, recovery_ids=ids
    )


@router.post("/process-next", response_model=IngestionRecoveryResponse | None)
def process_next(db: Annotated[Session, Depends(get_db)]):
    return process_next_recovery(db, _store(), _pipeline())
