import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.oms_schema import OmsSchemaRegistry
from app.schemas.oms_schema import OmsSchemaCreate


class OmsSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def register_oms_schema(db: Session, payload: OmsSchemaCreate) -> OmsSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise OmsSchemaConflict("OMS specification digest does not match content.")
    existing = db.scalar(select(OmsSchemaRegistry).where(OmsSchemaRegistry.name == payload.name, OmsSchemaRegistry.version == payload.version))
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise OmsSchemaConflict("OMS schema name and version are immutable.")
        return existing
    record = OmsSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
