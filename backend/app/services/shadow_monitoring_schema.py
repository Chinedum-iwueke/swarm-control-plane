import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shadow_monitoring_schema import ShadowMonitoringSchemaRegistry
from app.schemas.shadow_monitoring_schema import ShadowMonitoringSchemaCreate


class ShadowMonitoringSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_shadow_monitoring_schema(
    db: Session, payload: ShadowMonitoringSchemaCreate
) -> ShadowMonitoringSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ShadowMonitoringSchemaConflict(
            "Shadow-monitoring specification digest does not match content."
        )
    existing = db.scalar(
        select(ShadowMonitoringSchemaRegistry).where(
            ShadowMonitoringSchemaRegistry.name == payload.name,
            ShadowMonitoringSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ShadowMonitoringSchemaConflict(
                "Shadow-monitoring schema name and version are immutable."
            )
        return existing
    record = ShadowMonitoringSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
