import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_schedule_schema import ExecutionScheduleSchemaRegistry
from app.schemas.execution_schedule_schema import ExecutionScheduleSchemaCreate


class ExecutionScheduleSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_execution_schedule_schema(
    db: Session, payload: ExecutionScheduleSchemaCreate
) -> ExecutionScheduleSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionScheduleSchemaConflict(
            "Execution-schedule specification digest does not match content."
        )
    existing = db.scalar(
        select(ExecutionScheduleSchemaRegistry).where(
            ExecutionScheduleSchemaRegistry.name == payload.name,
            ExecutionScheduleSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionScheduleSchemaConflict(
                "Execution-schedule schema name and version are immutable."
            )
        return existing
    record = ExecutionScheduleSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
