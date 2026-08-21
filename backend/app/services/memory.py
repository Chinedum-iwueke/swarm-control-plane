from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.evidence import CanonicalEvidenceObject
from app.models.memory import (
    EvidenceDossier,
    EvidenceOppositionRecord,
    EvidenceOutcomeRecord,
)
from app.schemas.evidence import EvidenceObjectCreate
from app.schemas.memory import (
    BeliefLedgerCreate,
    DossierCompileCreate,
    EpisodePublishCreate,
    OppositionCreate,
    OppositionReviewCreate,
    OutcomeCreate,
)
from app.services.evidence import (
    EvidenceAccessContext,
    canonical_payload_digest,
    get_evidence_object,
    register_evidence_object,
)

_TERMS = re.compile(r"[a-z0-9][a-z0-9_-]*")
_ACCESS_LEVEL = {"public": 0, "internal": 1, "restricted": 2, "protected": 3}


def record_digest(document: object) -> str:
    if hasattr(document, "model_dump"):
        document = document.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def create_opposition(
    db: Session, payload: OppositionCreate, access: EvidenceAccessContext
) -> EvidenceOppositionRecord:
    claim = get_evidence_object(db, payload.subject_claim_id, access, audit=False)
    opposing = get_evidence_object(db, payload.opposing_object_id, access, audit=False)
    if claim.object_type != "claim":
        raise HTTPException(status_code=422, detail="Opposition subject must be a claim.")
    if claim.project != payload.project or opposing.project != payload.project:
        raise HTTPException(status_code=422, detail="Opposition must remain in one project.")
    document = payload.model_dump(mode="json") | {
        "status": "proposed",
        "supersedes_id": None,
    }
    return _commit(
        db,
        EvidenceOppositionRecord(
            project=payload.project,
            subject_claim_id=payload.subject_claim_id,
            opposing_object_id=payload.opposing_object_id,
            opposition_type=payload.opposition_type,
            comparability=payload.comparability.model_dump(mode="json"),
            rationale=payload.rationale,
            status="proposed",
            resolution=None,
            supersedes_id=None,
            record_digest=record_digest(document),
            recorded_by=payload.recorded_by,
        ),
        "Identical opposition record already exists.",
    )


def review_opposition(
    db: Session,
    opposition_id: UUID,
    payload: OppositionReviewCreate,
    access: EvidenceAccessContext,
) -> EvidenceOppositionRecord:
    previous = db.get(EvidenceOppositionRecord, opposition_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Opposition record not found.")
    get_evidence_object(db, previous.subject_claim_id, access, audit=False)
    already_reviewed = db.scalar(
        select(EvidenceOppositionRecord.id).where(
            EvidenceOppositionRecord.supersedes_id == previous.id
        )
    )
    if previous.supersedes_id is not None or previous.status != "proposed" or already_reviewed:
        raise HTTPException(status_code=409, detail="Only a proposed opposition may be reviewed.")
    document = {
        "previous_digest": previous.record_digest,
        **payload.model_dump(mode="json"),
    }
    return _commit(
        db,
        EvidenceOppositionRecord(
            project=previous.project,
            subject_claim_id=previous.subject_claim_id,
            opposing_object_id=previous.opposing_object_id,
            opposition_type=previous.opposition_type,
            comparability=previous.comparability,
            rationale=previous.rationale,
            status=payload.status,
            resolution=payload.resolution,
            supersedes_id=previous.id,
            record_digest=record_digest(document),
            recorded_by=payload.reviewed_by,
        ),
        "Opposition review already exists.",
    )


def record_outcome(
    db: Session, payload: OutcomeCreate, access: EvidenceAccessContext
) -> EvidenceOutcomeRecord:
    evidence = get_evidence_object(db, payload.evidence_object_id, access, audit=False)
    if evidence.project != payload.project:
        raise HTTPException(status_code=422, detail="Outcome project does not match evidence.")
    for claim_id in payload.affected_claim_ids:
        claim = get_evidence_object(db, claim_id, access, audit=False)
        if claim.object_type != "claim" or claim.project != payload.project:
            raise HTTPException(status_code=422, detail="Affected object must be a project claim.")
    document = payload.model_dump(mode="json")
    return _commit(
        db,
        EvidenceOutcomeRecord(
            project=payload.project,
            evidence_object_id=payload.evidence_object_id,
            outcome_kind=payload.outcome_kind,
            question=payload.question,
            scope=payload.scope.model_dump(mode="json"),
            method=payload.method,
            uncertainty=[item.model_dump(mode="json") for item in payload.uncertainty],
            failure_mechanisms=payload.failure_mechanisms,
            affected_claim_ids=payload.affected_claim_ids,
            record_digest=record_digest(document),
            recorded_by=payload.recorded_by,
        ),
        "Outcome record already exists.",
    )


def search_outcomes(
    db: Session,
    query: str,
    project: str,
    access: EvidenceAccessContext,
) -> dict:
    if "*" not in access.projects and project not in access.projects:
        raise HTTPException(status_code=403, detail="Evidence project access denied.")
    terms = set(_TERMS.findall(query.lower()))
    records = db.scalars(
        select(EvidenceOutcomeRecord)
        .where(EvidenceOutcomeRecord.project == project)
        .order_by(EvidenceOutcomeRecord.created_at.desc())
    ).all()
    matches = []
    for record in records:
        get_evidence_object(db, record.evidence_object_id, access, audit=False)
        material = " ".join(
            [
                record.question,
                record.method,
                *record.failure_mechanisms,
                *record.scope.get("limitations", []),
            ]
        )
        score = len(terms & set(_TERMS.findall(material.lower())))
        if score:
            matches.append((score, record))
    matches.sort(key=lambda item: (-item[0], str(item[1].id)))
    return {
        "query": query,
        "valid_negative": [item for _, item in matches if item.outcome_kind == "valid_negative"],
        "invalid_attempt": [item for _, item in matches if item.outcome_kind == "invalid_attempt"],
    }


def publish_belief(
    db: Session, payload: BeliefLedgerCreate, access: EvidenceAccessContext
) -> CanonicalEvidenceObject:
    belief_payload = {
        "kind": "belief",
        "claim_object_id": str(payload.claim_object_id),
        "supporting_evidence_ids": [str(item) for item in payload.supporting_evidence_ids],
        "opposing_evidence_ids": [str(item) for item in payload.opposing_evidence_ids],
        "assessment": payload.assessment.value,
        "confidence": None,
        "owner": payload.owner,
        "reviewers": payload.reviewers,
        "valid_from": payload.valid_from.isoformat(),
        "valid_until": payload.valid_until.isoformat() if payload.valid_until else None,
        "scope": payload.scope,
        "assessment_type": payload.assessment.kind,
        "typed_assessment": payload.assessment.model_dump(mode="json"),
        "synthesis_method": payload.synthesis_method,
        "uncertainty": [item.model_dump(mode="json") for item in payload.uncertainty],
        "dependencies": [str(item) for item in payload.dependencies],
        "minority_assessments": [
            item.model_dump(mode="json") for item in payload.minority_assessments
        ],
        "review_due": payload.review_due.isoformat(),
        "invalidation_conditions": payload.invalidation_conditions,
    }
    envelope = EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": payload.object_id,
            "object_type": "belief",
            "content_version": payload.content_version,
            "content_digest": canonical_payload_digest(belief_payload),
            "producer": {
                "system": "research-intelligence",
                "native_type": "belief",
                "native_id": str(payload.object_id),
                "schema_version": "belief-ledger-v1.0.0",
            },
            "aliases": [
                {
                    "namespace": "research-intelligence",
                    "object_type": "belief",
                    "value": str(payload.object_id),
                }
            ],
            "supersedes_object_id": payload.supersedes_object_id,
            "project": payload.project,
            "access_class": payload.access_class,
            "authority_class": "institutional",
            "payload": belief_payload,
            "created_by": payload.created_by,
        }
    )
    return register_evidence_object(db, envelope, access)


def publish_episode(
    db: Session, payload: EpisodePublishCreate, access: EvidenceAccessContext
) -> CanonicalEvidenceObject:
    if payload.dossier_id is not None:
        dossier = db.get(EvidenceDossier, payload.dossier_id)
        if dossier is None or dossier.project != payload.project:
            raise HTTPException(status_code=422, detail="Episode dossier is unavailable.")
    episode_payload = {
        "kind": "episode",
        "task_id": str(payload.task_id) if payload.task_id else None,
        "input_object_ids": [str(item) for item in payload.input_object_ids],
        "output_object_ids": [str(item) for item in payload.output_object_ids],
        "tools": payload.tools,
        "failures": payload.failures,
        "decision_object_ids": [str(item) for item in payload.decision_object_ids],
        "lessons": payload.lessons,
        "protected_references": payload.protected_references,
        "question": payload.question,
        "prior_belief_object_id": (
            str(payload.prior_belief_object_id)
            if payload.prior_belief_object_id
            else None
        ),
        "dossier_id": str(payload.dossier_id) if payload.dossier_id else None,
        "alternatives": payload.alternatives,
        "surprise": payload.surprise,
        "new_questions": payload.new_questions,
    }
    envelope = EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": payload.object_id,
            "object_type": "episode",
            "content_version": payload.content_version,
            "content_digest": canonical_payload_digest(episode_payload),
            "producer": {
                "system": "research-intelligence",
                "native_type": "episode",
                "native_id": str(payload.object_id),
                "schema_version": "episode-memory-v1.0.0",
            },
            "aliases": [
                {
                    "namespace": "research-intelligence",
                    "object_type": "episode",
                    "value": str(payload.object_id),
                }
            ],
            "project": payload.project,
            "access_class": payload.access_class,
            "authority_class": "operational",
            "payload": episode_payload,
            "created_by": payload.created_by,
        }
    )
    return register_evidence_object(db, envelope, access)


def compile_dossier(
    db: Session, payload: DossierCompileCreate, access: EvidenceAccessContext
) -> EvidenceDossier:
    if _ACCESS_LEVEL[payload.access_class] > _ACCESS_LEVEL[access.max_access_class]:
        raise HTTPException(
            status_code=403,
            detail="Dossier access class exceeds compiler access.",
        )
    dossier_access = EvidenceAccessContext(
        actor=access.actor,
        projects=access.projects,
        max_access_class=payload.access_class,
        may_write=access.may_write,
    )
    grouped_ids = {
        "claims": payload.claim_ids,
        "supporting_evidence": payload.supporting_evidence_ids,
        "opposing_evidence": payload.opposing_evidence_ids,
        "beliefs": payload.belief_ids,
        "episodes": payload.episode_ids,
    }
    _validate_object_types(db, payload.claim_ids, {"claim"}, "claims")
    _validate_object_types(db, payload.belief_ids, {"belief"}, "beliefs")
    _validate_object_types(db, payload.episode_ids, {"episode"}, "episodes")
    snapshots = {
        group: [_snapshot(db, object_id, payload.project, dossier_access) for object_id in ids]
        for group, ids in grouped_ids.items()
    }
    _validate_record_ids(
        db,
        payload.project,
        payload.opposition_record_ids,
        EvidenceOppositionRecord,
        "opposition",
    )
    _validate_record_ids(
        db,
        payload.project,
        payload.outcome_record_ids,
        EvidenceOutcomeRecord,
        "outcome",
    )
    document = {
        "scope": payload.scope,
        "doctrine_and_authority": payload.doctrine_and_authority,
        "objects": snapshots,
        "opposition_record_ids": [str(item) for item in payload.opposition_record_ids],
        "outcome_record_ids": [str(item) for item in payload.outcome_record_ids],
        "retrieval_manifest": payload.retrieval_manifest,
        "unknowns": payload.unknowns,
        "access_limitations": [
            item
            for records in snapshots.values()
            for item in records
            if item["access"] == "redacted"
        ],
        "risks": payload.risks,
        "dissent": payload.dissent,
        "synthesis": payload.synthesis,
        "recommendation": payload.recommendation,
    }
    digest_document = {
        **payload.model_dump(mode="json"),
        "dossier": document,
    }
    return _commit(
        db,
        EvidenceDossier(
            dossier_key=payload.dossier_key,
            version=payload.version,
            project=payload.project,
            access_class=payload.access_class,
            question=payload.question,
            decision_context=payload.decision_context,
            evidence_cutoff=payload.evidence_cutoff,
            dossier=document,
            record_digest=record_digest(digest_document),
            compiler_version=payload.compiler_version,
            compiled_by=payload.compiled_by,
            expires_at=payload.expires_at,
        ),
        "Dossier key, version, or digest already exists.",
    )


def replay_dossier(
    db: Session, dossier_id: UUID, access: EvidenceAccessContext
) -> tuple[EvidenceDossier, bool, list[dict]]:
    dossier = db.get(EvidenceDossier, dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Evidence dossier not found.")
    _require_dossier_access(dossier, access)
    impacts = []
    for group, snapshots in dossier.dossier["objects"].items():
        for snapshot in snapshots:
            if snapshot["access"] != "included":
                continue
            current = db.get(CanonicalEvidenceObject, UUID(snapshot["object_id"]))
            if current is None:
                impacts.append(
                    {"group": group, "object_id": snapshot["object_id"], "impact": "missing"}
                )
            elif current.content_digest != snapshot["content_digest"]:
                impacts.append(
                    {"group": group, "object_id": snapshot["object_id"], "impact": "digest_changed"}
                )
            else:
                from app.services.lifecycle import lifecycle_state

                state = lifecycle_state(db, current.id)
                if state is not None and state.state != "active":
                    impacts.append(
                        {
                            "group": group,
                            "object_id": snapshot["object_id"],
                            "impact": state.state,
                            "successor_object_id": (
                                str(state.successor_object_id)
                                if state.successor_object_id
                                else None
                            ),
                        }
                    )
                elif db.scalar(
                    select(CanonicalEvidenceObject.id).where(
                        CanonicalEvidenceObject.supersedes_object_id == current.id
                    )
                ) is not None:
                    impacts.append(
                        {
                            "group": group,
                            "object_id": snapshot["object_id"],
                            "impact": "superseded",
                        }
                    )
    return dossier, not impacts, impacts


def get_dossier(
    db: Session, dossier_id: UUID, access: EvidenceAccessContext
) -> EvidenceDossier:
    dossier = db.get(EvidenceDossier, dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Evidence dossier not found.")
    _require_dossier_access(dossier, access)
    return dossier


def list_dossiers(db: Session, access: EvidenceAccessContext) -> list[EvidenceDossier]:
    statement = select(EvidenceDossier)
    if "*" not in access.projects:
        statement = statement.where(EvidenceDossier.project.in_(access.projects))
    allowed = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    return list(
        db.scalars(
            statement.where(EvidenceDossier.access_class.in_(allowed)).order_by(
                EvidenceDossier.frozen_at.desc()
            )
        ).all()
    )


def _snapshot(
    db: Session,
    object_id: UUID,
    project: str,
    access: EvidenceAccessContext,
) -> dict:
    record = db.get(CanonicalEvidenceObject, object_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier evidence object not found.")
    if record.project != project:
        raise HTTPException(status_code=422, detail="Dossier evidence crosses projects.")
    try:
        get_evidence_object(db, object_id, access, audit=False)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        return {
            "object_id": str(object_id),
            "access": "redacted",
            "reason": "access_class_denied",
        }
    snapshot = {
        "object_id": str(record.id),
        "object_type": record.object_type,
        "content_version": record.content_version,
        "content_digest": record.content_digest,
        "access": "included",
        "coordinates": record.payload.get("coordinates"),
    }
    if snapshot["coordinates"]:
        snapshot["citation_replay_path"] = (
            f"/v1/research/retrieval/objects/{record.id}/replay"
        )
    return snapshot


def _validate_record_ids(db, project, ids, model, label) -> None:
    records = db.scalars(select(model).where(model.id.in_(ids))).all() if ids else []
    if len(records) != len(set(ids)) or any(item.project != project for item in records):
        raise HTTPException(status_code=422, detail=f"Dossier {label} records are invalid.")


def _validate_object_types(db, ids, allowed_types, label) -> None:
    records = db.scalars(
        select(CanonicalEvidenceObject).where(CanonicalEvidenceObject.id.in_(ids))
    ).all() if ids else []
    if len(records) != len(set(ids)) or any(
        item.object_type not in allowed_types for item in records
    ):
        raise HTTPException(status_code=422, detail=f"Dossier {label} are invalid.")


def _require_dossier_access(dossier, access) -> None:
    if "*" not in access.projects and dossier.project not in access.projects:
        raise HTTPException(status_code=403, detail="Dossier project access denied.")
    if _ACCESS_LEVEL[dossier.access_class] > _ACCESS_LEVEL[access.max_access_class]:
        raise HTTPException(status_code=403, detail="Dossier access class denied.")


def _commit(db: Session, record, conflict: str):
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc
    db.refresh(record)
    return record
