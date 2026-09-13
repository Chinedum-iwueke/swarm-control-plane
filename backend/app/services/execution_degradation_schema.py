import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_degradation_schema import ExecutionDegradationSchemaRegistry
from app.schemas.execution_degradation_schema import ExecutionDegradationSchemaCreate


class ExecutionDegradationSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_execution_degradation_schema(
    db: Session, payload: ExecutionDegradationSchemaCreate
) -> ExecutionDegradationSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionDegradationSchemaConflict(
            "Execution-degradation specification digest does not match content."
        )
    existing = db.scalar(
        select(ExecutionDegradationSchemaRegistry).where(
            ExecutionDegradationSchemaRegistry.name == payload.name,
            ExecutionDegradationSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionDegradationSchemaConflict(
                "Execution-degradation schema name and version are immutable."
            )
        return existing
    record = ExecutionDegradationSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
