from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.causal_pipeline import CausalDatasetMaterialization
from app.models.model_evaluation import ModelFamilyEvaluation
from app.models.selection_audit import SelectionBiasAudit
from app.schemas.model_evaluation import ModelFamilyEvaluationCreate
from app.services.research import record_digest


class ModelEvaluationConflict(RuntimeError):
    pass


def build_scorecard(
    payload: ModelFamilyEvaluationCreate,
    materialization: CausalDatasetMaterialization,
    audit: SelectionBiasAudit,
) -> dict:
    protocol = payload.protocol
    if record_digest(protocol) != payload.protocol_digest:
        raise ModelEvaluationConflict(
            "Evaluation protocol digest does not match content."
        )
    candidate_documents = [item.model_dump(mode="json") for item in payload.candidates]
    if record_digest(candidate_documents) != payload.candidates_digest:
        raise ModelEvaluationConflict("Candidate-set digest does not match content.")
    keys = [item.candidate_key for item in payload.candidates]
    if len(keys) != len(set(keys)):
        raise ModelEvaluationConflict("Candidate identities must be unique.")
    families = {item.family for item in payload.candidates}
    required_families = {
        "baseline",
        "supervised",
        "unsupervised",
        "regime",
        "meta_label",
    }
    if not required_families.issubset(families):
        raise ModelEvaluationConflict(
            "The complete required model-family ladder is absent."
        )
    baseline_kinds = {
        item.baseline_kind for item in payload.candidates if item.family == "baseline"
    }
    if baseline_kinds != {"unconditional", "linear"}:
        raise ModelEvaluationConflict(
            "Unconditional and linear baselines are both required."
        )
    expected_folds = [item["fold"] for item in materialization.fold_results]
    required_regimes = set(protocol.required_regimes)
    for candidate in payload.candidates:
        if [item.fold for item in candidate.fold_metrics] != expected_folds:
            raise ModelEvaluationConflict(
                f"Candidate {candidate.candidate_key} does not cover every causal fold in order."
            )
        if {item.regime for item in candidate.regime_metrics} != required_regimes:
            raise ModelEvaluationConflict(
                f"Candidate {candidate.candidate_key} does not cover the exact required regimes."
            )
    strongest_baseline = max(
        item.overall_primary_score
        for item in payload.candidates
        if item.family == "baseline"
    )
    evaluations = []
    for candidate in payload.candidates:
        regime_scores = [item.primary_score for item in candidate.regime_metrics]
        support_ok = all(
            item.observations >= protocol.minimum_regime_observations
            and min(item.positive_labels, item.negative_labels) / item.observations
            >= protocol.minimum_minority_fraction
            for item in candidate.regime_metrics
        )
        incremental = candidate.overall_primary_score - strongest_baseline
        dispersion = max(regime_scores) - min(regime_scores)
        reasons = []
        if candidate.family == "baseline":
            reasons.append("reference_baseline")
        else:
            if incremental < protocol.minimum_incremental_value:
                reasons.append("insufficient_incremental_value")
            if min(regime_scores) < protocol.minimum_regime_score:
                reasons.append("weak_regime")
            if dispersion > protocol.maximum_regime_dispersion:
                reasons.append("unstable_across_regimes")
            if candidate.permutation_primary_score > protocol.maximum_permutation_score:
                reasons.append("label_permutation_control_failed")
            if not support_ok:
                reasons.append("insufficient_class_support")
        evaluations.append(
            {
                "candidate_key": candidate.candidate_key,
                "family": candidate.family,
                "overall_primary_score": candidate.overall_primary_score,
                "incremental_value_vs_strongest_baseline": round(incremental, 12),
                "minimum_regime_score": min(regime_scores),
                "regime_dispersion": round(dispersion, 12),
                "permutation_primary_score": candidate.permutation_primary_score,
                "class_support_sufficient": support_ok,
                "qualified": candidate.family != "baseline" and not reasons,
                "reasons": reasons,
            }
        )
    ranked = sorted(
        evaluations,
        key=lambda item: (-item["overall_primary_score"], item["candidate_key"]),
    )
    return {
        "schema_version": "model-family-regime-scorecard-v1.0.0",
        "materialization_id": str(materialization.id),
        "materialization_digest": materialization.record_digest,
        "selection_audit_id": str(audit.id),
        "selection_audit_digest": audit.audit_digest,
        "protocol_digest": payload.protocol_digest,
        "candidates_digest": payload.candidates_digest,
        "strongest_baseline_score": strongest_baseline,
        "ranking": [
            {**item, "rank": index} for index, item in enumerate(ranked, start=1)
        ],
        "qualified_candidate_keys": [
            item["candidate_key"] for item in ranked if item["qualified"]
        ],
        "promotion_authority": False,
        "training_authority": False,
        "capital_authority": False,
    }


def register_evaluation(
    db: Session, payload: ModelFamilyEvaluationCreate
) -> ModelFamilyEvaluation:
    materialization = db.get(CausalDatasetMaterialization, payload.materialization_id)
    audit = db.get(SelectionBiasAudit, payload.selection_audit_id)
    if materialization is None:
        raise ModelEvaluationConflict("A verified ML-002 materialization is required.")
    if audit is None or audit.status != "active" or audit.conclusion == "blocked":
        raise ModelEvaluationConflict(
            "A current non-blocked DISC-007 selection audit is required."
        )
    scorecard = build_scorecard(payload, materialization, audit)
    scorecard_digest = record_digest(scorecard)
    existing = db.scalar(
        select(ModelFamilyEvaluation).where(
            or_(
                ModelFamilyEvaluation.evaluation_key == payload.evaluation_key,
                ModelFamilyEvaluation.scorecard_digest == scorecard_digest,
            )
        )
    )
    if existing:
        if existing.scorecard_digest == scorecard_digest:
            return existing
        raise ModelEvaluationConflict(
            "Evaluation key already exists with different evidence."
        )
    record = ModelFamilyEvaluation(
        evaluation_key=payload.evaluation_key,
        materialization_id=payload.materialization_id,
        selection_audit_id=payload.selection_audit_id,
        protocol=payload.protocol.model_dump(mode="json"),
        protocol_digest=payload.protocol_digest,
        candidates=[item.model_dump(mode="json") for item in payload.candidates],
        candidates_digest=payload.candidates_digest,
        scorecard=scorecard,
        scorecard_digest=scorecard_digest,
        evaluated_by=payload.evaluated_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ModelEvaluationConflict(
            "Evaluation key or digest already exists."
        ) from exc
    return record
