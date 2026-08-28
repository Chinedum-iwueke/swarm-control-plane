import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.microstructure_model import MicrostructureModelRegistry
from app.schemas.microstructure_model import MicrostructureModelCreate


class MicrostructureModelConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def register_model(db: Session, payload: MicrostructureModelCreate) -> MicrostructureModelRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise MicrostructureModelConflict("Microstructure model digest does not match content.")
    existing = db.scalar(select(MicrostructureModelRegistry).where(
        MicrostructureModelRegistry.name == payload.name, MicrostructureModelRegistry.version == payload.version
    ))
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise MicrostructureModelConflict("Microstructure model name and version are immutable.")
        return existing
    record = MicrostructureModelRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
