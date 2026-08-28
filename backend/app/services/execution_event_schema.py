import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_event_schema import ExecutionEventSchemaRegistry
from app.schemas.execution_event_schema import ExecutionEventSchemaCreate


class ExecutionEventSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def register_event_schema(db: Session, payload: ExecutionEventSchemaCreate) -> ExecutionEventSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionEventSchemaConflict("Event schema digest does not match content.")
    existing = db.scalar(
        select(ExecutionEventSchemaRegistry).where(
            ExecutionEventSchemaRegistry.name == payload.name,
            ExecutionEventSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionEventSchemaConflict("Event schema name and version are immutable.")
        return existing
    record = ExecutionEventSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
