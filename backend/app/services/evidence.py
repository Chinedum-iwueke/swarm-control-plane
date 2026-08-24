from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic_core import to_jsonable_python
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.evidence import (
    CanonicalEvidenceAuditEvent,
    CanonicalEvidenceEdge,
    CanonicalEvidenceObject,
    CanonicalIdentityAlias,
)
from app.schemas.evidence import (
    ArtifactPayload,
    EvidenceObjectCreate,
    EvidenceObjectResponse,
)

_ACCESS_LEVEL = {"public": 0, "internal": 1, "restricted": 2, "protected": 3}
_REFERENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "edition": ("source_object_id",),
    "artifact": ("edition_object_id",),
    "scientific_object": ("artifact_object_id", "parent_object_id"),
    "claim": ("evidence_object_ids",),
    "method": ("evidence_object_ids", "assumption_object_ids"),
    "assumption": ("evidence_object_ids",),
    "dataset": ("source_object_ids", "correction_object_ids"),
    "run": ("dataset_object_ids",),
    "result": ("run_object_id", "artifact_object_ids"),
    "review": ("subject_object_id",),
    "decision": ("evidence_object_ids",),
    "belief": (
        "claim_object_id",
        "supporting_evidence_ids",
        "opposing_evidence_ids",
        "dependencies",
    ),
    "episode": (
        "input_object_ids",
        "output_object_ids",
        "decision_object_ids",
        "prior_belief_object_id",
    ),
}


@dataclass(frozen=True)
class EvidenceAccessContext:
    actor: str
    projects: frozenset[str]
    max_access_class: str
    may_write: bool = False

    def __post_init__(self) -> None:
        if self.max_access_class not in _ACCESS_LEVEL:
            raise ValueError("unknown evidence access class")


ORCHESTRATOR_ACCESS = EvidenceAccessContext(
    actor="orchestrator",
    projects=frozenset({"*"}),
    max_access_class="protected",
    may_write=True,
)


def canonical_payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        to_jsonable_python(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def register_evidence_object(
    db: Session,
    payload: EvidenceObjectCreate,
    access: EvidenceAccessContext,
    *,
    commit: bool = True,
) -> CanonicalEvidenceObject:
    _require_write_access(access, payload.project, payload.access_class)
    _require_payload_digest(payload)

    existing = db.get(CanonicalEvidenceObject, payload.object_id)
    if existing is not None:
        if _stored_document(existing) == _create_document(payload):
            return existing
        raise HTTPException(status_code=409, detail="Canonical object identity is immutable.")

    references = _payload_references(payload)
    referenced = _load_references(db, references)
    _validate_references(payload, references, referenced)
    _validate_supersession(db, payload)
    _validate_aliases_available(db, payload)

    record = CanonicalEvidenceObject(
        id=payload.object_id,
        schema_version=payload.schema_version,
        object_schema_version=payload.object_schema_version,
        object_type=payload.object_type,
        content_version=payload.content_version,
        content_digest=payload.content_digest,
        producer=payload.producer.model_dump(mode="json"),
        supersedes_object_id=payload.supersedes_object_id,
        project=payload.project,
        access_class=payload.access_class,
        authority_class=payload.authority_class,
        payload=payload.payload.model_dump(mode="json"),
        created_by=payload.created_by,
    )
    db.add(record)
    db.flush()
    from app.services.lifecycle import (
        ensure_lifecycle_state,
        register_declared_supersession,
    )

    ensure_lifecycle_state(db, record.id)
    for alias in payload.aliases:
        db.add(
            CanonicalIdentityAlias(
                canonical_object_id=record.id,
                canonical_object_type=record.object_type,
                namespace=alias.namespace,
                native_object_type=alias.object_type,
                alias_value=alias.value,
                producer_schema_version=payload.producer.schema_version,
            )
        )
    for reference in references:
        db.add(
            CanonicalEvidenceEdge(
                subject_id=record.id,
                predicate="derived_from",
                object_id=reference,
            )
        )
    if payload.supersedes_object_id is not None:
        db.add(
            CanonicalEvidenceEdge(
                subject_id=record.id,
                predicate="supersedes",
                object_id=payload.supersedes_object_id,
            )
        )
        register_declared_supersession(
            db,
            referenced.get(payload.supersedes_object_id)
            or db.get(CanonicalEvidenceObject, payload.supersedes_object_id),
            record,
            access.actor,
        )
    db.add(
        CanonicalEvidenceAuditEvent(
            object_id=record.id,
            event_type="created",
            actor=access.actor,
            detail="Canonical evidence object registered.",
        )
    )
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def get_evidence_object(
    db: Session,
    object_id: UUID,
    access: EvidenceAccessContext,
    *,
    audit: bool = True,
) -> CanonicalEvidenceObject:
    record = db.get(CanonicalEvidenceObject, object_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Canonical evidence object not found.")
    _require_read_access(access, record)
    if audit:
        db.add(
            CanonicalEvidenceAuditEvent(
                object_id=record.id,
                event_type="read",
                actor=access.actor,
                detail="Canonical evidence object read.",
            )
        )
        db.commit()
    return record


def list_evidence_objects(
    db: Session,
    access: EvidenceAccessContext,
    *,
    object_type: str | None = None,
    project: str | None = None,
    limit: int = 100,
) -> list[CanonicalEvidenceObject]:
    statement = select(CanonicalEvidenceObject)
    allowed_projects = access.projects
    if "*" not in allowed_projects:
        statement = statement.where(CanonicalEvidenceObject.project.in_(allowed_projects))
    if project is not None:
        if "*" not in allowed_projects and project not in allowed_projects:
            raise HTTPException(status_code=403, detail="Evidence project access denied.")
        statement = statement.where(CanonicalEvidenceObject.project == project)
    if object_type is not None:
        statement = statement.where(CanonicalEvidenceObject.object_type == object_type)
    allowed_classes = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    statement = statement.where(CanonicalEvidenceObject.access_class.in_(allowed_classes))
    statement = statement.order_by(CanonicalEvidenceObject.created_at.desc()).limit(limit)
    return list(db.scalars(statement).all())


def get_evidence_lineage(
    db: Session,
    object_id: UUID,
    access: EvidenceAccessContext,
) -> tuple[CanonicalEvidenceObject, list[CanonicalEvidenceObject], list[CanonicalEvidenceObject]]:
    record = get_evidence_object(db, object_id, access)
    edges = db.scalars(
        select(CanonicalEvidenceEdge).where(
            or_(
                CanonicalEvidenceEdge.subject_id == object_id,
                CanonicalEvidenceEdge.object_id == object_id,
            )
        )
    ).all()
    ancestor_ids = {edge.object_id for edge in edges if edge.subject_id == object_id}
    descendant_ids = {edge.subject_id for edge in edges if edge.object_id == object_id}
    ancestors = [get_evidence_object(db, item, access, audit=False) for item in ancestor_ids]
    descendants = [
        get_evidence_object(db, item, access, audit=False) for item in descendant_ids
    ]
    return record, ancestors, descendants


def evidence_response(record: CanonicalEvidenceObject) -> EvidenceObjectResponse:
    if record.payload.get("tombstone") is True:
        raise HTTPException(
            status_code=410,
            detail="Evidence payload was lawfully deleted; lifecycle dossier remains available.",
        )
    aliases = [
        {
            "namespace": alias.namespace,
            "object_type": alias.native_object_type,
            "value": alias.alias_value,
        }
        for alias in getattr(record, "aliases", [])
    ]
    if not aliases:
        aliases = [
            {
                "namespace": record.producer["system"],
                "object_type": record.producer["native_type"],
                "value": record.producer["native_id"],
            }
        ]
    return EvidenceObjectResponse.model_validate(
        {
            "schema_version": record.schema_version,
            "object_schema_version": record.object_schema_version,
            "object_id": record.id,
            "object_type": record.object_type,
            "content_version": record.content_version,
            "content_digest": record.content_digest,
            "producer": record.producer,
            "aliases": aliases,
            "supersedes_object_id": record.supersedes_object_id,
            "project": record.project,
            "access_class": record.access_class,
            "authority_class": record.authority_class,
            "payload": record.payload,
            "created_by": record.created_by,
            "created_at": record.created_at,
        }
    )


def _create_document(payload: EvidenceObjectCreate) -> dict[str, Any]:
    document = payload.model_dump(mode="json")
    document["aliases"] = sorted(
        document["aliases"],
        key=lambda item: (item["namespace"], item["object_type"], item["value"]),
    )
    return document


def _stored_document(record: CanonicalEvidenceObject) -> dict[str, Any]:
    document = evidence_response(record).model_dump(
        mode="json", exclude={"created_at"}
    )
    document["aliases"] = sorted(
        document["aliases"],
        key=lambda item: (item["namespace"], item["object_type"], item["value"]),
    )
    return document


def _require_payload_digest(payload: EvidenceObjectCreate) -> None:
    if isinstance(payload.payload, ArtifactPayload):
        return
    actual = canonical_payload_digest(payload.payload.model_dump(mode="json"))
    if actual != payload.content_digest:
        raise HTTPException(status_code=422, detail="Canonical content digest mismatch.")


def _require_write_access(
    access: EvidenceAccessContext, project: str, access_class: str
) -> None:
    if not access.may_write:
        raise HTTPException(status_code=403, detail="Canonical evidence write denied.")
    if "*" not in access.projects and project not in access.projects:
        raise HTTPException(status_code=403, detail="Evidence project access denied.")
    if _ACCESS_LEVEL[access_class] > _ACCESS_LEVEL[access.max_access_class]:
        raise HTTPException(status_code=403, detail="Evidence access class denied.")


def _require_read_access(
    access: EvidenceAccessContext, record: CanonicalEvidenceObject
) -> None:
    if "*" not in access.projects and record.project not in access.projects:
        raise HTTPException(status_code=403, detail="Evidence project access denied.")
    if _ACCESS_LEVEL[record.access_class] > _ACCESS_LEVEL[access.max_access_class]:
        raise HTTPException(status_code=403, detail="Evidence access class denied.")


def _payload_references(payload: EvidenceObjectCreate) -> set[UUID]:
    document = payload.payload.model_dump()
    references: set[UUID] = set()
    for field in _REFERENCE_FIELDS.get(payload.object_type, ()):
        value = document.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            references.update(value)
        else:
            references.add(value)
    references.discard(payload.object_id)
    return references


def _load_references(
    db: Session, references: set[UUID]
) -> dict[UUID, CanonicalEvidenceObject]:
    if not references:
        return {}
    records = db.scalars(
        select(CanonicalEvidenceObject).where(CanonicalEvidenceObject.id.in_(references))
    ).all()
    return {record.id: record for record in records}


def _validate_references(
    payload: EvidenceObjectCreate,
    references: set[UUID],
    records: dict[UUID, CanonicalEvidenceObject],
) -> None:
    missing = references - records.keys()
    if missing:
        raise HTTPException(status_code=422, detail="Evidence lineage reference is missing.")
    for record in records.values():
        if record.project != payload.project:
            raise HTTPException(status_code=422, detail="Cross-project lineage is forbidden.")
        if _ACCESS_LEVEL[record.access_class] > _ACCESS_LEVEL[payload.access_class]:
            raise HTTPException(
                status_code=422,
                detail="Evidence cannot expose a more restricted lineage object.",
            )


def _validate_supersession(db: Session, payload: EvidenceObjectCreate) -> None:
    if payload.supersedes_object_id is None:
        return
    previous = db.get(CanonicalEvidenceObject, payload.supersedes_object_id)
    if previous is None:
        raise HTTPException(status_code=422, detail="Superseded object is missing.")
    if previous.object_type != payload.object_type or previous.project != payload.project:
        raise HTTPException(status_code=422, detail="Supersession identity is incompatible.")
    if previous.content_version == payload.content_version:
        raise HTTPException(status_code=422, detail="Successor content version must change.")


def _validate_aliases_available(db: Session, payload: EvidenceObjectCreate) -> None:
    for alias in payload.aliases:
        existing = db.scalar(
            select(CanonicalIdentityAlias).where(
                CanonicalIdentityAlias.namespace == alias.namespace,
                CanonicalIdentityAlias.native_object_type == alias.object_type,
                CanonicalIdentityAlias.alias_value == alias.value,
            )
        )
        if existing is not None and existing.canonical_object_id != payload.object_id:
            raise HTTPException(status_code=409, detail="Canonical alias is already owned.")
