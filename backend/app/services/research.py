import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchReview,
    ResearchSource,
    ResearchTrial,
)
from app.schemas.research import (
    ResearchDecisionCreate,
    ResearchExperimentCreate,
    ResearchHypothesisCreate,
    ResearchResultCreate,
    ResearchReviewCreate,
    ResearchSourceCreate,
    ResearchTrialCreate,
)


def record_digest(document: Any) -> str:
    if hasattr(document, "model_dump"):
        document = document.model_dump(mode="json")
    canonical = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _require_digest(actual: str, supplied: str, label: str) -> None:
    if actual != supplied:
        raise HTTPException(status_code=422, detail=f"{label} digest mismatch.")


def _commit(db: Session, record: Any, conflict: str) -> Any:
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc
    db.refresh(record)
    return record


def register_source(db: Session, payload: ResearchSourceCreate) -> ResearchSource:
    _require_digest(
        record_digest(payload.specification), payload.record_digest, "Source"
    )
    return _commit(
        db,
        ResearchSource(
            source_key=payload.source_key,
            specification=payload.specification.model_dump(mode="json"),
            record_digest=payload.record_digest,
            registered_by=payload.registered_by,
        ),
        "Source key or digest already exists.",
    )


def register_hypothesis(
    db: Session, payload: ResearchHypothesisCreate
) -> ResearchHypothesis:
    _require_digest(
        record_digest(payload.specification), payload.record_digest, "Hypothesis"
    )
    return _commit(
        db,
        ResearchHypothesis(
            hypothesis_key=payload.hypothesis_key,
            trial_family=payload.trial_family,
            specification=payload.specification.model_dump(mode="json"),
            record_digest=payload.record_digest,
            registered_by=payload.registered_by,
        ),
        "Hypothesis key or digest already exists.",
    )


def register_experiment(
    db: Session, payload: ResearchExperimentCreate
) -> ResearchExperiment:
    hypothesis = db.get(ResearchHypothesis, payload.hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found.")
    if db.get(ResearchSource, payload.source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    hypothesis_approved = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "hypothesis",
            ResearchReview.subject_id == hypothesis.id,
            ResearchReview.subject_digest == hypothesis.record_digest,
            ResearchReview.review_kind == "approval",
            ResearchReview.verdict == "approved",
        )
    )
    if hypothesis_approved is None:
        raise HTTPException(status_code=409, detail="Exact hypothesis is not approved.")
    _require_digest(
        record_digest(payload.manifest), payload.manifest_digest, "Experiment manifest"
    )
    return _commit(
        db,
        ResearchExperiment(
            experiment_key=payload.experiment_key,
            hypothesis_id=payload.hypothesis_id,
            source_id=payload.source_id,
            manifest=payload.manifest.model_dump(mode="json"),
            manifest_digest=payload.manifest_digest,
            registered_by=payload.registered_by,
        ),
        "Experiment key or manifest digest already exists.",
    )


def add_review(
    db: Session,
    subject_type: str,
    subject_id: UUID,
    payload: ResearchReviewCreate,
) -> ResearchReview:
    model, digest_field = {
        "hypothesis": (ResearchHypothesis, "record_digest"),
        "experiment": (ResearchExperiment, "manifest_digest"),
        "result": (ResearchResult, "record_digest"),
    }[subject_type]
    subject = db.get(model, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Review subject not found.")
    expected = getattr(subject, digest_field)
    _require_digest(expected, payload.subject_digest, "Review subject")
    if (
        payload.review_kind == "approval"
        and subject_type in {"hypothesis", "experiment"}
        and subject.registered_by == payload.reviewer
    ):
        raise HTTPException(
            status_code=422, detail="A record author cannot approve their own record."
        )
    if subject_type == "result":
        trial = db.get(ResearchTrial, subject.trial_id)
        if trial is not None and trial.executed_by == payload.reviewer:
            raise HTTPException(
                status_code=422,
                detail="Result reviewer must be independent from the executor.",
            )
    document = {
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        **payload.model_dump(mode="json"),
    }
    return _commit(
        db,
        ResearchReview(
            subject_type=subject_type,
            subject_id=subject_id,
            subject_digest=payload.subject_digest,
            review_kind=payload.review_kind,
            verdict=payload.verdict,
            review=payload.review,
            record_digest=record_digest(document),
            reviewer=payload.reviewer,
        ),
        "This reviewer already recorded that review for this subject.",
    )


def register_trial(
    db: Session, experiment_id: UUID, payload: ResearchTrialCreate
) -> ResearchTrial:
    experiment = db.get(ResearchExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    _require_digest(experiment.manifest_digest, payload.experiment_digest, "Experiment")
    approved = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "experiment",
            ResearchReview.subject_id == experiment.id,
            ResearchReview.subject_digest == experiment.manifest_digest,
            ResearchReview.review_kind == "approval",
            ResearchReview.verdict == "approved",
        )
    )
    if approved is None:
        raise HTTPException(
            status_code=409, detail="Exact experiment manifest is not approved."
        )
    hypothesis = db.get(ResearchHypothesis, experiment.hypothesis_id)
    assert hypothesis is not None
    db.scalars(
        select(ResearchHypothesis)
        .where(ResearchHypothesis.trial_family == hypothesis.trial_family)
        .with_for_update()
    ).all()
    family_count = (
        db.scalar(
            select(func.count(ResearchTrial.id)).where(
                ResearchTrial.trial_family == hypothesis.trial_family
            )
        )
        or 0
    )
    maximum = int(hypothesis.specification["maximum_trials"])
    if family_count >= maximum:
        raise HTTPException(status_code=409, detail="Trial-family budget is exhausted.")
    trial_number = family_count + 1
    document = {
        "experiment_digest": payload.experiment_digest,
        "trial_number": trial_number,
        "plan": payload.plan.model_dump(mode="json"),
        "executed_by": payload.executed_by,
    }
    _require_digest(record_digest(document), payload.record_digest, "Trial")
    return _commit(
        db,
        ResearchTrial(
            experiment_id=experiment.id,
            trial_family=hypothesis.trial_family,
            run_id=payload.plan.run_id,
            trial_number=trial_number,
            plan=payload.plan.model_dump(mode="json"),
            record_digest=payload.record_digest,
            executed_by=payload.executed_by,
        ),
        "Trial run, digest, or family sequence already exists.",
    )


def register_result(
    db: Session, trial_id: UUID, payload: ResearchResultCreate
) -> ResearchResult:
    trial = db.get(ResearchTrial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    _require_digest(trial.record_digest, payload.trial_digest, "Trial")
    document = {
        "trial_digest": payload.trial_digest,
        "outcome": payload.outcome,
        "result": payload.result.model_dump(mode="json"),
        "recorded_by": payload.recorded_by,
    }
    _require_digest(record_digest(document), payload.record_digest, "Result")
    return _commit(
        db,
        ResearchResult(
            trial_id=trial.id,
            outcome=payload.outcome,
            result=payload.result.model_dump(mode="json"),
            record_digest=payload.record_digest,
            recorded_by=payload.recorded_by,
        ),
        "A result already exists for this trial or digest.",
    )


def register_decision(
    db: Session, result_id: UUID, payload: ResearchDecisionCreate
) -> ResearchDecision:
    result = db.get(ResearchResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    _require_digest(result.record_digest, payload.result_digest, "Result")
    independent_review = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "result",
            ResearchReview.subject_id == result.id,
            ResearchReview.subject_digest == result.record_digest,
            ResearchReview.review_kind.in_(
                ("independent_review", "adversarial_review")
            ),
        )
    )
    if independent_review is None:
        raise HTTPException(
            status_code=409, detail="Independent result review required."
        )
    document = payload.model_dump(mode="json") | {"result_id": str(result_id)}
    return _commit(
        db,
        ResearchDecision(
            result_id=result.id,
            decision=payload.decision,
            rationale=payload.rationale,
            result_digest=payload.result_digest,
            record_digest=record_digest(document),
            decided_by=payload.decided_by,
        ),
        "Decision digest already exists.",
    )
