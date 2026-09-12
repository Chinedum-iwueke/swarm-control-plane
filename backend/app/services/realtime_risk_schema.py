import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.realtime_risk_schema import RealtimeRiskSchemaRegistry
from app.schemas.realtime_risk_schema import RealtimeRiskSchemaCreate


class RealtimeRiskSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_realtime_risk_schema(
    db: Session, payload: RealtimeRiskSchemaCreate
) -> RealtimeRiskSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise RealtimeRiskSchemaConflict(
            "Real-time risk specification digest does not match content."
        )
    existing = db.scalar(
        select(RealtimeRiskSchemaRegistry).where(
            RealtimeRiskSchemaRegistry.name == payload.name,
            RealtimeRiskSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise RealtimeRiskSchemaConflict(
                "Real-time risk schema name and version are immutable."
            )
        return existing
    record = RealtimeRiskSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
