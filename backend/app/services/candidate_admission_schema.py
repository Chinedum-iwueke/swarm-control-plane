import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_admission_schema import CandidateAdmissionSchemaRegistry
from app.schemas.candidate_admission_schema import CandidateAdmissionSchemaCreate


class CandidateAdmissionSchemaConflict(RuntimeError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def register_candidate_admission_schema(
    db: Session, payload: CandidateAdmissionSchemaCreate
) -> CandidateAdmissionSchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise CandidateAdmissionSchemaConflict(
            "Candidate-admission specification digest does not match content."
        )
    existing = db.scalar(
        select(CandidateAdmissionSchemaRegistry).where(
            CandidateAdmissionSchemaRegistry.name == payload.name,
            CandidateAdmissionSchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise CandidateAdmissionSchemaConflict(
                "Candidate-admission schema name and version are immutable."
            )
        return existing
    record = CandidateAdmissionSchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record
