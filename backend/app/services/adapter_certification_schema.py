import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.adapter_certification_schema import AdapterCertificationSchemaRegistry
from app.schemas.adapter_certification_schema import AdapterCertificationSchemaCreate


class AdapterCertificationSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_adapter_certification_schema(
    db: Session, payload: AdapterCertificationSchemaCreate
) -> AdapterCertificationSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise AdapterCertificationSchemaConflict(
            "Adapter-certification specification digest does not match content."
        )
    existing = db.scalar(
        select(AdapterCertificationSchemaRegistry).where(
            AdapterCertificationSchemaRegistry.name == payload.name,
            AdapterCertificationSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise AdapterCertificationSchemaConflict(
                "Adapter-certification schema name and version are immutable."
            )
        return existing
    record = AdapterCertificationSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
