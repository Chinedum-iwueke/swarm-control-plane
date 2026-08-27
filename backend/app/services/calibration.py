from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.calibration import ModelCalibrationAssessment
from app.models.memory import EvidenceDossier
from app.models.model_evaluation import ModelFamilyEvaluation
from app.schemas.calibration import CalibrationAssessmentCreate
from app.services.research import record_digest


class CalibrationConflict(RuntimeError):
    pass


def _expected_abstention(receipt, policy):
    if receipt.expected_calibration_error > policy.maximum_expected_calibration_error:
        return True, "miscalibrated"
    if (
        receipt.shift_distance > policy.maximum_shift_distance
        or receipt.applicability == "out_of_support"
    ):
        return True, "distribution_shift"
    if receipt.support_count < policy.minimum_support:
        return True, "low_support"
    if receipt.uncertainty > policy.maximum_uncertainty:
        return True, "high_uncertainty"
    return False, "none"


def build_assessment(
    payload: CalibrationAssessmentCreate,
    evaluation: ModelFamilyEvaluation,
    dossier: EvidenceDossier,
) -> tuple[dict, str]:
    specification = payload.specification
    if record_digest(specification) != payload.specification_digest:
        raise CalibrationConflict(
            "Calibration specification digest does not match content."
        )
    qualified = set(evaluation.scorecard.get("qualified_candidate_keys", []))
    if payload.candidate_key not in qualified:
        raise CalibrationConflict(
            "Candidate was not qualified by the bound ML-003 evaluation."
        )
    total = sum(item.observations for item in specification.reliability_bins)
    ece = (
        sum(
            item.observations * abs(item.mean_probability - item.observed_frequency)
            for item in specification.reliability_bins
        )
        / total
    )
    receipt_failures = []
    for receipt in specification.scenario_receipts:
        expected_abstained, expected_reason = _expected_abstention(
            receipt, specification.policy
        )
        if (
            receipt.abstained != expected_abstained
            or receipt.abstention_reason != expected_reason
        ):
            receipt_failures.append(receipt.scenario)
    slices_supported = all(
        item.supported
        == (
            item.observations >= specification.policy.minimum_support
            and item.calibration_error
            <= specification.policy.maximum_expected_calibration_error
            and item.shift_distance <= specification.policy.maximum_shift_distance
        )
        for item in specification.applicability_slices
    )
    failures = []
    if ece > specification.policy.maximum_expected_calibration_error:
        failures.append("miscalibrated")
    if (
        specification.uncertainty.empirical_coverage
        < specification.policy.minimum_empirical_coverage
    ):
        failures.append("undercoverage")
    if (
        specification.explanation.fidelity_score
        < specification.policy.minimum_explanation_fidelity
    ):
        failures.append("misleading_explanation")
    if not slices_supported:
        failures.append("applicability_misclassified")
    if receipt_failures:
        failures.append("abstention_policy_mismatch")
    status = "qualified" if not failures else "demotion_required"
    assessment = {
        "schema_version": "calibration-assessment-v1.0.0",
        "evaluation_id": str(evaluation.id),
        "evaluation_digest": evaluation.scorecard_digest,
        "dossier_id": str(dossier.id),
        "dossier_digest": dossier.record_digest,
        "candidate_key": payload.candidate_key,
        "specification_digest": payload.specification_digest,
        "expected_calibration_error": round(ece, 12),
        "empirical_coverage": specification.uncertainty.empirical_coverage,
        "mean_interval_width": specification.uncertainty.mean_interval_width,
        "explanation_fidelity": specification.explanation.fidelity_score,
        "applicability_slices_consistent": slices_supported,
        "scenario_receipts_valid": not receipt_failures,
        "scenario_failures": receipt_failures,
        "status": status,
        "failures": failures,
        "mandatory_abstention": True,
        "demotion_proposed": status == "demotion_required",
        "activation_authority": False,
        "promotion_authority": False,
        "capital_authority": False,
    }
    return assessment, status


def register_assessment(
    db: Session, payload: CalibrationAssessmentCreate
) -> ModelCalibrationAssessment:
    evaluation = db.get(ModelFamilyEvaluation, payload.evaluation_id)
    dossier = db.get(EvidenceDossier, payload.dossier_id)
    if evaluation is None or dossier is None:
        raise CalibrationConflict(
            "Registered ML-003 evaluation and RI-004 dossier are required."
        )
    assessment, status = build_assessment(payload, evaluation, dossier)
    assessment_digest = record_digest(assessment)
    existing = db.scalar(
        select(ModelCalibrationAssessment).where(
            or_(
                ModelCalibrationAssessment.assessment_key == payload.assessment_key,
                ModelCalibrationAssessment.assessment_digest == assessment_digest,
            )
        )
    )
    if existing:
        if existing.assessment_digest == assessment_digest:
            return existing
        raise CalibrationConflict(
            "Assessment key already exists with different evidence."
        )
    record = ModelCalibrationAssessment(
        assessment_key=payload.assessment_key,
        evaluation_id=payload.evaluation_id,
        dossier_id=payload.dossier_id,
        candidate_key=payload.candidate_key,
        specification=payload.specification.model_dump(mode="json"),
        specification_digest=payload.specification_digest,
        assessment=assessment,
        assessment_digest=assessment_digest,
        status=status,
        assessed_by=payload.assessed_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise CalibrationConflict("Assessment key or digest already exists.") from exc
    return record
