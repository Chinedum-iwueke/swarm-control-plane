import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.demo_certification_schema import DemoCertificationSchemaRegistry
from app.schemas.demo_certification_schema import DemoCertificationSchemaCreate


class DemoCertificationSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def register_demo_certification_schema(db: Session, payload: DemoCertificationSchemaCreate) -> DemoCertificationSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise DemoCertificationSchemaConflict("Demo-certification specification digest does not match content.")
    existing = db.scalar(select(DemoCertificationSchemaRegistry).where(
        DemoCertificationSchemaRegistry.name == payload.name,
        DemoCertificationSchemaRegistry.version == payload.version,
    ))
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise DemoCertificationSchemaConflict("Demo-certification schema name and version are immutable.")
        return existing
    record = DemoCertificationSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
