from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.schemas.market_data_catalog import (
    MarketDataCatalogCreate,
    MarketDataCatalogResponse,
    MarketDataResolution,
    MarketDataResolveRequest,
)
from app.services.market_data_catalog import (
    MarketDataConflict,
    MarketDataUnknown,
    register_catalog,
    resolve_market_data,
)

router = APIRouter(
    prefix="/v1/research/market-data-catalog",
    tags=["research-market-data-catalog"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/snapshots", response_model=MarketDataCatalogResponse, status_code=201)
def create_catalog(
    payload: MarketDataCatalogCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_catalog(db, payload)
        db.commit()
        db.refresh(record)
        return MarketDataCatalogResponse.model_validate(record)
    except MarketDataUnknown as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MarketDataConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/snapshots", response_model=list[MarketDataCatalogResponse])
def list_catalogs(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    records = db.scalars(
        select(MarketDataCatalogSnapshot)
        .order_by(MarketDataCatalogSnapshot.as_of.desc())
        .limit(limit)
    ).all()
    return [MarketDataCatalogResponse.model_validate(record) for record in records]


@router.get("/snapshots/{catalog_id}", response_model=MarketDataCatalogResponse)
def get_catalog(catalog_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(MarketDataCatalogSnapshot, catalog_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market-data catalog not found.")
    return MarketDataCatalogResponse.model_validate(record)


@router.post("/resolve", response_model=MarketDataResolution)
def resolve(payload: MarketDataResolveRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        return resolve_market_data(db, payload)
    except MarketDataUnknown as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MarketDataConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
