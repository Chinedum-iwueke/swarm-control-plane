from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CanonicalEvidenceObject,
    EvidenceGraphProjectionState,
    EvidenceRetrievalState,
    ResearchDecision,
    ResearchExperiment,
    ResearchResult,
    ResearchReview,
    ResearchTrial,
)
from app.models.laboratory import LaboratoryPublication, LaboratoryPublicationEvent
from app.schemas.evidence import EvidenceObjectCreate
from app.schemas.laboratory import (
    LaboratoryPublicationCreate,
    MemoryReceiptCreate,
    ProjectionReceiptCreate,
    PublicationFailureCreate,
)
from app.services.evidence import (
    ORCHESTRATOR_ACCESS,
    canonical_payload_digest,
    register_evidence_object,
)

SCHEMA_VERSION = "laboratory-publication-v1.0.0"
_NAMESPACE = uuid.UUID("f9bd28eb-6351-4a11-b872-2b0cfcb80a39")


def digest_document(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def create_publication(
    db: Session, payload: LaboratoryPublicationCreate
) -> LaboratoryPublication:
    _require_request_digest(payload)
    existing = db.scalar(
        select(LaboratoryPublication).where(
            LaboratoryPublication.request_digest == payload.request_digest
        )
    )
    if existing is not None:
        return existing

    trial, result, experiment, run, reviews, decision = _load_registry_lineage(
        db, payload
    )
    existing = db.scalar(
        select(LaboratoryPublication).where(
            LaboratoryPublication.request_digest == payload.request_digest
        )
    )
    if existing is not None:
        return existing
    _validate_lineage(payload, trial, result, experiment, run)
    publication_id = uuid.uuid5(_NAMESPACE, payload.request_digest)

    result_object = _register(
        db,
        native_type="result",
        native_id=str(result.id),
        authority="derived",
        payload={
            "kind": "result",
            "run_object_id": str(run.id),
            "outcome": _canonical_outcome(result.outcome),
            "metrics": result.result.get("metrics", {}),
            "artifact_object_ids": [],
        },
        created_by="research-registry",
    )
    review_objects = [
        _register(
            db,
            native_type="review",
            native_id=str(review.id),
            authority="institutional",
            payload={
                "kind": "review",
                "subject_object_id": str(result_object.id),
                "subject_digest": result_object.content_digest,
                "reviewer_authority": review.reviewer,
                "verdict": _canonical_verdict(review.verdict),
                "rationale": str(review.review.get("summary") or review.review),
            },
            created_by=review.reviewer,
        )
        for review in reviews
    ]
    decision_object = _register(
        db,
        native_type="decision",
        native_id=str(decision.id),
        authority="institutional",
        payload={
            "kind": "decision",
            "evidence_object_ids": [
                str(result_object.id),
                *(str(item.id) for item in review_objects),
            ],
            "decided_by_authority": decision.decided_by,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "valid_from": decision.decided_at,
            "valid_until": None,
        },
        created_by=decision.decided_by,
    )
    dossier_object = _register(
        db,
        native_type="episode",
        native_id=str(publication_id),
        authority="operational",
        payload={
            "kind": "episode",
            "task_id": None,
            "input_object_ids": [str(run.id)],
            "output_object_ids": [
                str(result_object.id),
                *(str(item.id) for item in review_objects),
            ],
            "tools": ["bulletproof-bt", "hermes-laboratory-publication"],
            "failures": [],
            "decision_object_ids": [str(decision_object.id)],
            "lessons": [
                "Negative, null, invalid, and inconclusive results remain canonical evidence."
            ],
            "protected_references": [f"bundle://sha256/{payload.bundle_digest}"],
            "question": None,
            "prior_belief_object_id": None,
            "dossier_id": publication_id,
            "alternatives": [],
            "surprise": None,
            "new_questions": [],
        },
        created_by="research-registry",
    )
    canonical_receipt = {
        "schema_version": "laboratory-canonical-receipt-v1.0.0",
        "run_object_id": str(run.id),
        "result_object_id": str(result_object.id),
        "review_object_ids": [str(item.id) for item in review_objects],
        "decision_object_id": str(decision_object.id),
        "dossier_object_id": str(dossier_object.id),
        "canonical_digest": digest_document(
            [
                str(run.id),
                str(result_object.id),
                *[str(item.id) for item in review_objects],
                str(decision_object.id),
                str(dossier_object.id),
            ]
        ),
    }
    publication = LaboratoryPublication(
        id=publication_id,
        trial_id=trial.id,
        result_id=result.id,
        run_object_id=run.id,
        request_digest=payload.request_digest,
        bundle_digest=payload.bundle_digest,
        state="awaiting_projections",
        lineage=payload.model_dump(mode="json", exclude={"request_digest"}),
        canonical_receipt=canonical_receipt,
        projection_receipt={},
        memory_receipt={},
        failure={},
    )
    db.add(publication)
    db.flush()
    _event(db, publication, "canonical_committed", canonical_receipt)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = db.scalar(
            select(LaboratoryPublication).where(
                LaboratoryPublication.request_digest == payload.request_digest
            )
        )
        if winner is not None:
            return winner
        raise HTTPException(
            status_code=409, detail="Publication lineage is already bound."
        ) from exc
    db.refresh(publication)
    return publication


def record_projection_receipt(
    db: Session, publication_id: UUID, payload: ProjectionReceiptCreate
) -> LaboratoryPublication:
    publication = _publication_for_update(db, publication_id)
    graph = db.get(EvidenceGraphProjectionState, "canonical-knowledge-graph")
    retrieval = db.get(EvidenceRetrievalState, "canonical-scientific")
    if graph is None or retrieval is None:
        raise HTTPException(
            status_code=409, detail="Canonical projections are not built."
        )
    if (
        graph.manifest_digest != payload.graph_manifest_digest
        or graph.source_epoch != payload.graph_source_epoch
        or retrieval.corpus_digest != payload.retrieval_corpus_digest
        or retrieval.source_epoch != payload.retrieval_source_epoch
    ):
        raise HTTPException(
            status_code=409,
            detail="Projection receipt does not match current projections.",
        )
    document = payload.model_dump(mode="json")
    if publication.projection_receipt == document:
        return publication
    if publication.projection_receipt and publication.projection_receipt != document:
        raise HTTPException(status_code=409, detail="Projection receipt is immutable.")
    publication.projection_receipt = document
    publication.state = "awaiting_memory"
    publication.failure = {}
    publication.updated_at = datetime.now(UTC)
    _event(db, publication, "projections_confirmed", document)
    db.commit()
    db.refresh(publication)
    return publication


def record_memory_receipt(
    db: Session, publication_id: UUID, payload: MemoryReceiptCreate
) -> LaboratoryPublication:
    publication = _publication_for_update(db, publication_id)
    if not publication.projection_receipt:
        raise HTTPException(
            status_code=409, detail="Projection confirmation is required first."
        )
    if payload.bundle_digest != publication.bundle_digest:
        raise HTTPException(
            status_code=409, detail="Memory receipt bundle digest mismatch."
        )
    document = payload.model_dump(mode="json")
    if publication.memory_receipt == document:
        return publication
    if publication.memory_receipt and publication.memory_receipt != document:
        raise HTTPException(status_code=409, detail="Memory receipt is immutable.")
    publication.memory_receipt = document
    publication.state = "complete"
    publication.failure = {}
    publication.completed_at = datetime.now(UTC)
    publication.updated_at = publication.completed_at
    _event(db, publication, "memory_confirmed", document)
    _event(
        db,
        publication,
        "publication_completed",
        {"bundle_digest": publication.bundle_digest},
    )
    db.commit()
    db.refresh(publication)
    return publication


def record_failure(
    db: Session, publication_id: UUID, payload: PublicationFailureCreate
) -> LaboratoryPublication:
    publication = _publication_for_update(db, publication_id)
    if publication.state == "complete":
        raise HTTPException(
            status_code=409, detail="Completed publication cannot fail."
        )
    publication.failure = payload.model_dump(mode="json")
    publication.state = f"{payload.stage}_failed"
    publication.updated_at = datetime.now(UTC)
    _event(db, publication, f"{payload.stage}_failed", publication.failure)
    db.commit()
    db.refresh(publication)
    return publication


def get_publication(db: Session, publication_id: UUID) -> LaboratoryPublication:
    record = db.get(LaboratoryPublication, publication_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Laboratory publication not found.")
    return record


def publication_events(
    db: Session, publication_id: UUID
) -> list[LaboratoryPublicationEvent]:
    get_publication(db, publication_id)
    return list(
        db.scalars(
            select(LaboratoryPublicationEvent)
            .where(LaboratoryPublicationEvent.publication_id == publication_id)
            .order_by(LaboratoryPublicationEvent.sequence)
        ).all()
    )


def _load_registry_lineage(db: Session, payload: LaboratoryPublicationCreate):
    trial = db.scalar(
        select(ResearchTrial)
        .where(ResearchTrial.id == payload.trial_id)
        .with_for_update()
    )
    result = db.get(ResearchResult, payload.result_id)
    if trial is None or result is None or result.trial_id != payload.trial_id:
        raise HTTPException(
            status_code=404, detail="Registered trial result was not found."
        )
    experiment = db.get(ResearchExperiment, trial.experiment_id)
    run = db.get(CanonicalEvidenceObject, payload.run_object_id)
    if experiment is None or run is None or run.object_type != "run":
        raise HTTPException(
            status_code=404, detail="Registered experiment run evidence was not found."
        )
    reviews = list(
        db.scalars(
            select(ResearchReview)
            .where(
                ResearchReview.subject_type == "result",
                ResearchReview.subject_id == result.id,
                ResearchReview.subject_digest == result.record_digest,
                ResearchReview.review_kind.in_(
                    ("independent_review", "adversarial_review")
                ),
            )
            .order_by(ResearchReview.review_kind)
        ).all()
    )
    decision = db.scalar(
        select(ResearchDecision).where(
            ResearchDecision.result_id == result.id,
            ResearchDecision.result_digest == result.record_digest,
        )
    )
    if (
        len(reviews) != 2
        or len({item.reviewer for item in reviews}) != 2
        or decision is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Two independent reviews and a decision are required.",
        )
    return trial, result, experiment, run, reviews, decision


def _validate_lineage(payload, trial, result, experiment, run) -> None:
    expected_commit = experiment.manifest.get("repository_commit")
    if expected_commit != payload.repository_commit:
        raise HTTPException(
            status_code=409, detail="Repository commit digest mismatch."
        )
    if trial.plan.get("dataset_digest") != payload.dataset_digest:
        raise HTTPException(status_code=409, detail="Dataset digest mismatch.")
    if run.payload.get("bundle_digest") != payload.bundle_digest:
        raise HTTPException(status_code=409, detail="Run bundle digest mismatch.")
    if run.payload.get("bundle_manifest_digest") != payload.bundle_manifest_digest:
        raise HTTPException(
            status_code=409, detail="Run bundle manifest digest mismatch."
        )
    if (
        run.payload.get("market_model_bundle_digest")
        != payload.market_model_bundle_digest
    ):
        raise HTTPException(
            status_code=409, detail="Market-model bundle digest mismatch."
        )
    if (
        run.payload.get("representation_contract_digest")
        != payload.representation_contract_digest
    ):
        raise HTTPException(
            status_code=409, detail="Representation contract digest mismatch."
        )
    if run.payload.get("code_digest") != trial.plan.get("engine_digest"):
        raise HTTPException(
            status_code=409, detail="Run code digest does not match the trial plan."
        )


def _require_request_digest(payload: LaboratoryPublicationCreate) -> None:
    document = payload.model_dump(mode="json", exclude={"request_digest"})
    if digest_document(document) != payload.request_digest:
        raise HTTPException(
            status_code=422, detail="Publication request digest mismatch."
        )


def _register(
    db: Session,
    *,
    native_type: str,
    native_id: str,
    authority: str,
    payload: dict,
    created_by: str,
):
    content_digest = canonical_payload_digest(payload)
    object_id = uuid.uuid5(_NAMESPACE, f"{native_type}:{native_id}:{content_digest}")
    item = EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": object_id,
            "object_type": native_type,
            "content_version": "1",
            "content_digest": content_digest,
            "producer": {
                "system": "hermes-laboratory",
                "native_type": native_type,
                "native_id": native_id,
                "schema_version": SCHEMA_VERSION,
            },
            "aliases": [
                {
                    "namespace": "hermes-laboratory",
                    "object_type": native_type,
                    "value": native_id,
                }
            ],
            "supersedes_object_id": None,
            "project": "bulletproof-bt",
            "access_class": "restricted",
            "authority_class": authority,
            "payload": payload,
            "created_by": created_by,
        }
    )
    return register_evidence_object(db, item, ORCHESTRATOR_ACCESS, commit=False)


def _canonical_outcome(value: str) -> str:
    return {
        "accepted": "positive",
        "positive": "positive",
        "rejected": "negative",
        "negative": "negative",
        "failed": "invalid",
        "invalid": "invalid",
        "null": "null",
        "inconclusive": "inconclusive",
    }.get(value, "inconclusive")


def _canonical_verdict(value: str) -> str:
    return (
        value
        if value in {"approved", "rejected", "needs_changes", "inconclusive"}
        else "inconclusive"
    )


def _publication_for_update(db: Session, publication_id: UUID) -> LaboratoryPublication:
    record = db.scalar(
        select(LaboratoryPublication)
        .where(LaboratoryPublication.id == publication_id)
        .with_for_update()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Laboratory publication not found.")
    return record


def _event(
    db: Session, publication: LaboratoryPublication, event_type: str, detail: dict
) -> None:
    sequence = (
        db.scalar(
            select(func.max(LaboratoryPublicationEvent.sequence)).where(
                LaboratoryPublicationEvent.publication_id == publication.id
            )
        )
        or 0
    ) + 1
    material = {
        "publication_id": str(publication.id),
        "sequence": sequence,
        "event_type": event_type,
        "detail": detail,
    }
    db.add(
        LaboratoryPublicationEvent(
            publication_id=publication.id,
            sequence=sequence,
            event_type=event_type,
            detail=detail,
            record_digest=digest_document(material),
        )
    )
    db.flush()
