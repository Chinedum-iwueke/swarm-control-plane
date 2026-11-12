from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CanonicalEvidenceEdge,
    ResearchDataSnapshot,
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchReview,
    ResearchSource,
    ResearchTrial,
)
from app.models.alpha_discovery import AlphaDiscoveryCandidate
from app.schemas.evidence import EvidenceObjectCreate
from app.schemas.graph import CanonicalEdgeCreate
from app.services.evidence import (
    ORCHESTRATOR_ACCESS,
    canonical_payload_digest,
    register_evidence_object,
)
from app.services.graph import register_edge

_PROJECT = "systematic-research"
_SCHEMA_VERSION = "canonical-identity-v1.0.0"
_OBJECT_SCHEMA_VERSION = "canonical-evidence-v1.0.0"
_PRODUCER_SCHEMA_VERSION = "research-registry-v1.0.0"


def _authority(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-._")
    if not normalized or not normalized[0].isalpha():
        normalized = f"research-{normalized or 'registry'}"
    return normalized[:100]


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_universe(document: dict[str, Any]) -> list[str]:
    data = document.get("data")
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail="Canonical research candidate data contract is missing.",
        )
    instruments = data.get("instruments")
    if isinstance(instruments, list) and instruments:
        return instruments
    instrument = data.get("instrument")
    if isinstance(instrument, str) and instrument:
        return [instrument]
    raise HTTPException(
        status_code=422,
        detail="Canonical research candidate universe is missing.",
    )


def _object(
    *,
    record: Any,
    object_type: str,
    payload: dict[str, Any],
    actor: str,
    authority_class: str,
    content_version: str,
) -> EvidenceObjectCreate:
    native_id = str(record.id)
    request = EvidenceObjectCreate.model_validate(
        {
            "schema_version": _SCHEMA_VERSION,
            "object_schema_version": _OBJECT_SCHEMA_VERSION,
            "object_id": record.id,
            "object_type": object_type,
            "content_version": content_version,
            "content_digest": "0" * 64,
            "producer": {
                "system": "research-registry",
                "native_type": object_type,
                "native_id": native_id,
                "schema_version": _PRODUCER_SCHEMA_VERSION,
            },
            "aliases": [
                {
                    "namespace": "research-registry",
                    "object_type": object_type,
                    "value": native_id,
                }
            ],
            "project": _PROJECT,
            "access_class": "internal",
            "authority_class": authority_class,
            "payload": payload,
            "created_by": _authority(actor),
        }
    )
    return request.model_copy(
        update={
            "content_digest": canonical_payload_digest(
                request.payload.model_dump(mode="json")
            )
        }
    )


def _edge(
    db: Session,
    *,
    subject_id,
    predicate: str,
    object_id,
    provenance_object_id,
    actor: str,
) -> None:
    existing = db.scalar(
        select(CanonicalEvidenceEdge).where(
            CanonicalEvidenceEdge.subject_id == subject_id,
            CanonicalEvidenceEdge.predicate == predicate,
            CanonicalEvidenceEdge.object_id == object_id,
        )
    )
    if existing is not None:
        return
    register_edge(
        db,
        CanonicalEdgeCreate.model_validate(
            {
                "subject_id": subject_id,
                "predicate": predicate,
                "object_id": object_id,
                "provenance_object_id": provenance_object_id,
                "access_class": "internal",
                "created_by": _authority(actor),
            }
        ),
        ORCHESTRATOR_ACCESS,
        commit=False,
    )


def publish_research_record(db: Session, record: Any) -> None:
    """Publish one native research record and its truthful canonical relationships."""

    if isinstance(record, ResearchSource):
        spec = record.specification
        payload = {
            "kind": "source",
            "title": spec["title"],
            "origin": spec["provenance"],
            "rights": "governed internal research use",
            "acquired_at": spec.get("observed_at") or record.registered_at,
        }
        request = _object(
            record=record,
            object_type="source",
            payload=payload,
            actor=record.registered_by,
            authority_class="primary",
            content_version=spec["version"],
        )
    elif isinstance(record, ResearchDataSnapshot):
        payload = {
            "kind": "dataset",
            "source_object_ids": [record.source_id],
            "schema_digest": _digest(record.specification),
            "partition_digests": [record.content_digest],
            "availability_policy": (
                "Point-in-time research snapshot; access and correction are governed "
                "by the native research registry."
            ),
            "correction_object_ids": [],
        }
        request = _object(
            record=record,
            object_type="dataset",
            payload=payload,
            actor=record.registered_by,
            authority_class="derived",
            content_version=record.snapshot_key,
        )
    elif isinstance(record, ResearchHypothesis):
        payload = {"kind": "hypothesis", **record.specification, "status": "proposed"}
        request = _object(
            record=record,
            object_type="hypothesis",
            payload=payload,
            actor=record.registered_by,
            authority_class="derived",
            content_version=record.hypothesis_key,
        )
    elif isinstance(record, AlphaDiscoveryCandidate):
        document = record.document
        if "evidence_object_ids" not in document:
            raise HTTPException(
                status_code=422,
                detail="Invalid discovery output is retained natively but is not a canonical research candidate.",
            )
        payload = {
            "kind": "research_candidate",
            "title": document["title"],
            "research_question": record.question,
            "predictor": document["predictor"],
            "target": document["target"],
            "horizon": document["horizon"],
            "causal_timing": document["causal_timing"],
            "null_hypothesis": document["null_hypothesis"],
            "predicted_direction": document["predicted_direction"],
            "mechanism": document["mechanism"],
            "rival_explanations": document["rival_explanations"],
            "falsification_criteria": document["falsification_criteria"],
            "universe": _candidate_universe(document),
            "parameter_budget": document["parameter_budget"],
            "data_contract": document["data"],
            "representation_plan": document.get("representation_plan"),
            "evidence_object_ids": document["evidence_object_ids"],
            "disposition": record.disposition,
            "reason_codes": record.reason_codes,
        }
        request = _object(
            record=record,
            object_type="research_candidate",
            payload=payload,
            actor="alpha-continuous-director",
            authority_class="derived",
            content_version=record.candidate_key,
        )
    elif isinstance(record, ResearchExperiment):
        evidence_ids = [record.hypothesis_id, record.source_id]
        if record.snapshot_id is not None:
            evidence_ids.append(record.snapshot_id)
        payload = {
            "kind": "method",
            "name": record.experiment_key,
            "procedure": json.dumps(record.manifest, sort_keys=True, default=str),
            "evidence_object_ids": evidence_ids,
            "assumption_object_ids": [],
        }
        request = _object(
            record=record,
            object_type="method",
            payload=payload,
            actor=record.registered_by,
            authority_class="derived",
            content_version=record.manifest_digest,
        )
    elif isinstance(record, ResearchTrial):
        experiment = db.get(ResearchExperiment, record.experiment_id)
        if experiment is None or experiment.snapshot_id is None:
            raise HTTPException(
                status_code=409,
                detail="A canonical run requires an immutable research data snapshot.",
            )
        plan = record.plan
        payload = {
            "kind": "run",
            "dataset_object_ids": [experiment.snapshot_id],
            "specification_digest": experiment.manifest_digest,
            "code_digest": _digest(
                {"repository": experiment.manifest["repository"], "commit": plan["code_commit"]}
            ),
            "environment_digest": plan["engine_digest"],
            "search_plan_digest": record.record_digest,
            "attempt": record.trial_number,
        }
        request = _object(
            record=record,
            object_type="run",
            payload=payload,
            actor=record.executed_by,
            authority_class="operational",
            content_version=record.run_id,
        )
    elif isinstance(record, ResearchResult):
        payload = {
            "kind": "result",
            "run_object_id": record.trial_id,
            "outcome": {
                "accepted": "positive",
                "rejected": "negative",
                "failed": "invalid",
                "inconclusive": "inconclusive",
            }[record.outcome],
            "metrics": record.result["metrics"],
            "artifact_object_ids": [],
        }
        request = _object(
            record=record,
            object_type="result",
            payload=payload,
            actor=record.recorded_by,
            authority_class="derived",
            content_version=record.record_digest,
        )
    elif isinstance(record, ResearchReview):
        payload = {
            "kind": "review",
            "subject_object_id": record.subject_id,
            "subject_digest": record.subject_digest,
            "reviewer_authority": _authority(record.reviewer),
            "verdict": record.verdict,
            "rationale": json.dumps(record.review, sort_keys=True, default=str),
        }
        request = _object(
            record=record,
            object_type="review",
            payload=payload,
            actor=record.reviewer,
            authority_class="institutional",
            content_version=record.record_digest,
        )
    elif isinstance(record, ResearchDecision):
        payload = {
            "kind": "decision",
            "evidence_object_ids": [record.result_id],
            "decided_by_authority": _authority(record.decided_by),
            "decision": record.decision,
            "rationale": record.rationale,
            "valid_from": record.decided_at,
        }
        request = _object(
            record=record,
            object_type="decision",
            payload=payload,
            actor=record.decided_by,
            authority_class="institutional",
            content_version=record.record_digest,
        )
    else:
        return

    register_evidence_object(db, request, ORCHESTRATOR_ACCESS, commit=False)

    if isinstance(record, ResearchExperiment):
        _edge(
            db,
            subject_id=record.hypothesis_id,
            predicate="uses_method",
            object_id=record.id,
            provenance_object_id=record.id,
            actor=record.registered_by,
        )
        if record.snapshot_id is not None:
            _edge(
                db,
                subject_id=record.hypothesis_id,
                predicate="uses_dataset",
                object_id=record.snapshot_id,
                provenance_object_id=record.id,
                actor=record.registered_by,
            )
    elif isinstance(record, ResearchTrial):
        experiment = db.get(ResearchExperiment, record.experiment_id)
        assert experiment is not None and experiment.snapshot_id is not None
        _edge(
            db,
            subject_id=record.id,
            predicate="uses_method",
            object_id=experiment.id,
            provenance_object_id=record.id,
            actor=record.executed_by,
        )
        _edge(
            db,
            subject_id=record.id,
            predicate="uses_dataset",
            object_id=experiment.snapshot_id,
            provenance_object_id=record.id,
            actor=record.executed_by,
        )
        _edge(
            db,
            subject_id=record.id,
            predicate="belongs_to_trial_family",
            object_id=experiment.hypothesis_id,
            provenance_object_id=record.id,
            actor=record.executed_by,
        )
    elif isinstance(record, ResearchResult):
        trial = db.get(ResearchTrial, record.trial_id)
        if trial is None:
            raise HTTPException(status_code=409, detail="Canonical result run is missing.")
        experiment = db.get(ResearchExperiment, trial.experiment_id)
        if experiment is None:
            raise HTTPException(status_code=409, detail="Canonical result method is missing.")
        _edge(
            db,
            subject_id=record.trial_id,
            predicate="produced_result",
            object_id=record.id,
            provenance_object_id=record.id,
            actor=record.recorded_by,
        )
        _edge(
            db,
            subject_id=record.id,
            predicate="belongs_to_trial_family",
            object_id=experiment.hypothesis_id,
            provenance_object_id=record.id,
            actor=record.recorded_by,
        )
    elif isinstance(record, ResearchReview):
        _edge(
            db,
            subject_id=record.id,
            predicate="reviews",
            object_id=record.subject_id,
            provenance_object_id=record.id,
            actor=record.reviewer,
        )
    elif isinstance(record, ResearchDecision):
        _edge(
            db,
            subject_id=record.id,
            predicate="decides_on",
            object_id=record.result_id,
            provenance_object_id=record.id,
            actor=record.decided_by,
        )


def backfill_research_evidence(db: Session, *, limit_per_type: int = 500) -> dict[str, Any]:
    """Idempotently publish a bounded native-registry slice in dependency order."""

    models = (
        ResearchSource,
        ResearchDataSnapshot,
        ResearchHypothesis,
        AlphaDiscoveryCandidate,
        ResearchExperiment,
        ResearchTrial,
        ResearchResult,
        ResearchReview,
        ResearchDecision,
    )
    report: dict[str, Any] = {"published": {}, "skipped": []}
    for model in models:
        records = db.scalars(select(model).order_by(model.id).limit(limit_per_type)).all()
        count = 0
        for record in records:
            try:
                publish_research_record(db, record)
                db.commit()
                count += 1
            except HTTPException as exc:
                db.rollback()
                report["skipped"].append(
                    {
                        "native_type": model.__name__,
                        "native_id": str(record.id),
                        "reason": str(exc.detail),
                    }
                )
        report["published"][model.__name__] = count
    report["limit_per_type"] = limit_per_type
    report["success"] = not report["skipped"]
    return report
