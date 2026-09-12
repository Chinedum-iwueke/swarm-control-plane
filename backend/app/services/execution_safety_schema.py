import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_safety_schema import ExecutionSafetySchemaRegistry
from app.schemas.execution_safety_schema import ExecutionSafetySchemaCreate


class ExecutionSafetySchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def register_execution_safety_schema(db: Session, payload: ExecutionSafetySchemaCreate) -> ExecutionSafetySchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionSafetySchemaConflict("Execution-safety specification digest does not match content.")
    existing = db.scalar(select(ExecutionSafetySchemaRegistry).where(
        ExecutionSafetySchemaRegistry.name == payload.name,
        ExecutionSafetySchemaRegistry.version == payload.version,
    ))
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionSafetySchemaConflict("Execution-safety schema name and version are immutable.")
        return existing
    record = ExecutionSafetySchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
