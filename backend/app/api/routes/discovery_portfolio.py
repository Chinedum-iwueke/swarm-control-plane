import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.discovery_portfolio import DiscoveryPortfolio
from app.schemas.discovery_portfolio import (
    DiscoveryPortfolioCreate,
    DiscoveryPortfolioResponse,
)
from app.services.discovery_portfolio import register_portfolio, serialize_portfolio

router = APIRouter(
    prefix="/v1/research/discovery-portfolios",
    tags=["discovery-information-gain"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "", response_model=DiscoveryPortfolioResponse, status_code=status.HTTP_201_CREATED
)
def create(payload: DiscoveryPortfolioCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        portfolio = register_portfolio(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Portfolio version or allocation digest already exists."
        ) from exc
    db.refresh(portfolio)
    return DiscoveryPortfolioResponse.model_validate(serialize_portfolio(db, portfolio))


@router.get("", response_model=list[DiscoveryPortfolioResponse])
def list_portfolios(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    records = db.scalars(
        select(DiscoveryPortfolio)
        .order_by(DiscoveryPortfolio.created_at.desc())
        .limit(limit)
    ).all()
    return [
        DiscoveryPortfolioResponse.model_validate(serialize_portfolio(db, record))
        for record in records
    ]


@router.get("/{portfolio_id}", response_model=DiscoveryPortfolioResponse)
def get(portfolio_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    portfolio = db.get(DiscoveryPortfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "Discovery portfolio not found.")
    return DiscoveryPortfolioResponse.model_validate(serialize_portfolio(db, portfolio))
