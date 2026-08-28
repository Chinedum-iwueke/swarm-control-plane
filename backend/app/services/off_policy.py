from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.calibration import ModelCalibrationAssessment
from app.models.off_policy import OffPolicyProposalEvaluation
from app.models.offline_rl import OfflineRLDatasetContract
from app.models.selection_audit import SelectionBiasAudit
from app.schemas.off_policy import OffPolicyEvaluationCreate
from app.services.research import record_digest


class OffPolicyConflict(RuntimeError):
    pass


def build_evaluation(
    payload: OffPolicyEvaluationCreate,
    dataset: OfflineRLDatasetContract,
    audit: SelectionBiasAudit,
    calibration: ModelCalibrationAssessment,
) -> tuple[dict, str]:
    proposal = payload.proposal
    if record_digest(proposal) != payload.proposal_digest:
        raise OffPolicyConflict("Off-policy proposal digest does not match content.")
    if dataset.status != "qualified":
        raise OffPolicyConflict("A qualified RL-001 dataset contract is required.")
    if audit.status != "active" or audit.conclusion == "blocked":
        raise OffPolicyConflict("A current non-blocked DISC-007 audit is required.")
    if calibration.status != "qualified":
        raise OffPolicyConflict(
            "A qualified ML-004 calibration assessment is required."
        )
    if calibration.candidate_key != proposal.base_candidate_key:
        raise OffPolicyConflict("Target policy does not match the ML-004 candidate.")
    allowed_estimators = set(dataset.contract["evaluation"]["estimators"])
    submitted_estimators = {item.estimator for item in proposal.estimators}
    if not submitted_estimators.issubset(allowed_estimators):
        raise OffPolicyConflict("Proposal uses an estimator absent from RL-001.")
    failures: list[str] = []
    estimator_lowers = [item.lower_confidence_bound for item in proposal.estimators]
    estimator_points = [item.point_estimate for item in proposal.estimators]
    stress_lowers = [item.lower_bound for item in proposal.stresses]
    conservative_value = min(estimator_lowers + stress_lowers)
    estimator_spread = max(estimator_points) - min(estimator_points)
    if conservative_value < proposal.gate.minimum_conservative_value:
        failures.append("conservative_value_below_floor")
    if estimator_spread > proposal.gate.maximum_estimator_spread:
        failures.append("estimator_disagreement")
    if any(
        item.effective_sample_size < proposal.gate.minimum_effective_sample_size
        for item in proposal.estimators
    ):
        failures.append("weak_effective_sample_size")
    if any(
        item.maximum_importance_weight > proposal.gate.maximum_importance_weight
        for item in proposal.estimators
    ):
        failures.append("unsafe_importance_weight")
    if proposal.support.minimum_overlap < proposal.gate.minimum_overlap:
        failures.append("weak_overlap")
    if (
        proposal.support.extrapolation_fraction
        > proposal.gate.maximum_extrapolation_fraction
    ):
        failures.append("excess_extrapolation")
    if proposal.support.unsupported_actions:
        failures.append("unsupported_actions")
    if any(
        item.lower_bound < proposal.gate.minimum_conservative_value
        for item in proposal.stresses
    ):
        failures.append("stress_failure")
    decision = "shadow_eligible" if not failures else "rejected"
    evaluation = {
        "schema_version": "conservative-off-policy-evaluation-v1.0.0",
        "dataset_contract_id": str(dataset.id),
        "dataset_audit_digest": dataset.audit_digest,
        "selection_audit_id": str(audit.id),
        "selection_audit_digest": audit.audit_digest,
        "calibration_assessment_id": str(calibration.id),
        "calibration_assessment_digest": calibration.assessment_digest,
        "target_policy_digest": proposal.target_policy_digest,
        "proposal_digest": payload.proposal_digest,
        "conservative_value": round(conservative_value, 12),
        "estimator_spread": round(estimator_spread, 12),
        "minimum_overlap": proposal.support.minimum_overlap,
        "maximum_extrapolation_fraction": proposal.support.extrapolation_fraction,
        "failures": failures,
        "decision": decision,
        "validation_environment": "shadow",
        "causal_policy_claim_authority": False,
        "deployment_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    return evaluation, decision


def register_evaluation(
    db: Session, payload: OffPolicyEvaluationCreate
) -> OffPolicyProposalEvaluation:
    dataset = db.get(OfflineRLDatasetContract, payload.dataset_contract_id)
    audit = db.get(SelectionBiasAudit, payload.selection_audit_id)
    calibration = db.get(ModelCalibrationAssessment, payload.calibration_assessment_id)
    if dataset is None or audit is None or calibration is None:
        raise OffPolicyConflict(
            "RL-001, DISC-007 and ML-004 dependencies are required."
        )
    evaluation, decision = build_evaluation(payload, dataset, audit, calibration)
    evaluation_digest = record_digest(evaluation)
    existing = db.scalar(
        select(OffPolicyProposalEvaluation).where(
            or_(
                OffPolicyProposalEvaluation.evaluation_key == payload.evaluation_key,
                OffPolicyProposalEvaluation.evaluation_digest == evaluation_digest,
            )
        )
    )
    if existing:
        if existing.evaluation_digest == evaluation_digest:
            return existing
        raise OffPolicyConflict(
            "Evaluation key already exists with different evidence."
        )
    record = OffPolicyProposalEvaluation(
        evaluation_key=payload.evaluation_key,
        dataset_contract_id=payload.dataset_contract_id,
        selection_audit_id=payload.selection_audit_id,
        calibration_assessment_id=payload.calibration_assessment_id,
        proposal=payload.proposal.model_dump(mode="json"),
        proposal_digest=payload.proposal_digest,
        evaluation=evaluation,
        evaluation_digest=evaluation_digest,
        decision=decision,
        evaluated_by=payload.evaluated_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise OffPolicyConflict("Evaluation key or digest already exists.") from exc
    return record
