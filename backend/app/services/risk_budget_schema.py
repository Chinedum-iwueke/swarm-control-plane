import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk_budget_schema import RiskBudgetSchemaRegistry
from app.schemas.risk_budget_schema import RiskBudgetSchemaCreate


class RiskBudgetSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def register_risk_budget_schema(db: Session, payload: RiskBudgetSchemaCreate) -> RiskBudgetSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise RiskBudgetSchemaConflict("Risk-budget specification digest does not match content.")
    existing = db.scalar(
        select(RiskBudgetSchemaRegistry).where(
            RiskBudgetSchemaRegistry.name == payload.name,
            RiskBudgetSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise RiskBudgetSchemaConflict("Risk-budget schema name and version are immutable.")
        return existing
    record = RiskBudgetSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
