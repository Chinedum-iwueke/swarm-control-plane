import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.venue_identity import VenueIdentityRegistry
from app.schemas.venue_identity import VenueIdentityCreate


class VenueIdentityConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_venue_identity(
    db: Session, payload: VenueIdentityCreate
) -> VenueIdentityRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise VenueIdentityConflict("Venue identity specification digest does not match content.")
    existing = db.scalar(
        select(VenueIdentityRegistry).where(
            VenueIdentityRegistry.name == payload.name,
            VenueIdentityRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise VenueIdentityConflict("Venue identity name and version are immutable.")
        return existing
    record = VenueIdentityRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
