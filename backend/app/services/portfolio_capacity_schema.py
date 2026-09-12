import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_capacity_schema import PortfolioCapacitySchemaRegistry
from app.schemas.portfolio_capacity_schema import PortfolioCapacitySchemaCreate


class PortfolioCapacitySchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def register_portfolio_capacity_schema(
    db: Session, payload: PortfolioCapacitySchemaCreate
) -> PortfolioCapacitySchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise PortfolioCapacitySchemaConflict("Portfolio-capacity specification digest does not match content.")
    existing = db.scalar(
        select(PortfolioCapacitySchemaRegistry).where(
            PortfolioCapacitySchemaRegistry.name == payload.name,
            PortfolioCapacitySchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise PortfolioCapacitySchemaConflict("Portfolio-capacity schema name and version are immutable.")
        return existing
    record = PortfolioCapacitySchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
