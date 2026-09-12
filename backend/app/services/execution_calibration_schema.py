import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_calibration_schema import ExecutionCalibrationSchemaRegistry
from app.schemas.execution_calibration_schema import ExecutionCalibrationSchemaCreate


class ExecutionCalibrationSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_execution_calibration_schema(
    db: Session, payload: ExecutionCalibrationSchemaCreate
) -> ExecutionCalibrationSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionCalibrationSchemaConflict(
            "Execution-calibration specification digest does not match content."
        )
    existing = db.scalar(
        select(ExecutionCalibrationSchemaRegistry).where(
            ExecutionCalibrationSchemaRegistry.name == payload.name,
            ExecutionCalibrationSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionCalibrationSchemaConflict(
                "Execution-calibration schema name and version are immutable."
            )
        return existing
    record = ExecutionCalibrationSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
