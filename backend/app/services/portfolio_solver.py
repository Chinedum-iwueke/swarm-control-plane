import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_solver import PortfolioSolverRegistry
from app.schemas.portfolio_solver import PortfolioSolverCreate


class PortfolioSolverConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def register_solver(db: Session, payload: PortfolioSolverCreate) -> PortfolioSolverRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise PortfolioSolverConflict("Solver specification digest does not match content.")
    existing = db.scalar(
        select(PortfolioSolverRegistry).where(
            PortfolioSolverRegistry.name == payload.name,
            PortfolioSolverRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise PortfolioSolverConflict("Solver name and version are immutable.")
        return existing
    record = PortfolioSolverRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
