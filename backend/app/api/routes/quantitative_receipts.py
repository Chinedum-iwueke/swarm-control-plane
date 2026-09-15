from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.schemas.quantitative_receipt import (
    QuantitativeReceiptCreate,
    QuantitativeReceiptResponse,
)
from app.services.quantitative_receipt import (
    QuantitativeReceiptConflict,
    lake_inventory_summary,
    register_receipt,
)

router = APIRouter(
    prefix="/v1/research/quantitative-receipts",
    tags=["research-quantitative-receipts"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=QuantitativeReceiptResponse, status_code=201)
def create_receipt(
    payload: QuantitativeReceiptCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_receipt(db, payload)
        db.commit()
        db.refresh(record)
        return QuantitativeReceiptResponse.model_validate(record)
    except QuantitativeReceiptConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[QuantitativeReceiptResponse])
def list_receipts(db: Annotated[Session, Depends(get_db)]):
    return [
        QuantitativeReceiptResponse.model_validate(item)
        for item in db.scalars(
            select(QuantitativeProducerReceipt).order_by(
                QuantitativeProducerReceipt.registered_at.desc()
            )
        ).all()
    ]


@router.get("/lake-inventory")
def lake_inventory(db: Annotated[Session, Depends(get_db)]):
    return lake_inventory_summary(db)


@router.get("/{receipt_id}", response_model=QuantitativeReceiptResponse)
def get_receipt(receipt_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(QuantitativeProducerReceipt, receipt_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Quantitative receipt not found.")
    return QuantitativeReceiptResponse.model_validate(record)
