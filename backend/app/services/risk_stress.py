from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.risk_stress import RiskStressAssessment
from app.schemas.risk_stress import RiskStressAssessmentCreate
from app.services.research import record_digest


class RiskStressConflict(RuntimeError):
    pass


def build_dossier(payload: RiskStressAssessmentCreate) -> tuple[dict, str]:
    request = payload.request
    if record_digest(request) != payload.request_digest:
        raise RiskStressConflict("Risk stress request digest does not match content.")
    failures: list[str] = []
    if request.evidence_age_seconds > request.limits.maximum_evidence_age_seconds:
        failures.append("stale_evidence")
    if request.drawdown.maximum_drawdown > request.limits.maximum_drawdown:
        failures.append("drawdown_limit_breached")
    if request.tail.expected_shortfall_upper_bound > request.limits.maximum_tail_loss:
        failures.append("tail_limit_breached")
    breached_scenarios = sorted(
        item.scenario
        for item in request.scenarios
        if item.uncertainty_upper_bound > request.limits.maximum_scenario_loss
    )
    if breached_scenarios:
        failures.append("scenario_limit_breached")
    reverse_by_name = {item.scenario: item for item in request.reverse_stresses}
    inconsistent_reverse = sorted(
        item.scenario
        for item in request.scenarios
        if reverse_by_name[item.scenario].breach_limit
        != request.limits.maximum_scenario_loss
    )
    if inconsistent_reverse:
        raise RiskStressConflict(
            "Reverse-stress limits must match the scenario loss limit."
        )
    worst = max(request.scenarios, key=lambda item: item.uncertainty_upper_bound)
    decision = "admissible" if not failures else "blocked"
    dossier = {
        "schema_version": "risk-stress-dossier-v1.0.0",
        "candidate_digest": request.candidate_digest,
        "portfolio_state_digest": request.portfolio_state_digest,
        "bulletproof_run_digest": request.bulletproof_run_digest,
        "cost_model_digest": request.cost_model_digest,
        "scenario_pack_version": request.scenario_pack_version,
        "scenario_pack_digest": request.scenario_pack_digest,
        "evidence_age_seconds": request.evidence_age_seconds,
        "maximum_drawdown": request.drawdown.maximum_drawdown,
        "maximum_drawdown_duration_periods": request.drawdown.maximum_duration_periods,
        "tail_loss_upper_bound": request.tail.expected_shortfall_upper_bound,
        "tail_method": request.tail.method,
        "worst_scenario": worst.scenario,
        "worst_scenario_loss_upper_bound": worst.uncertainty_upper_bound,
        "breached_scenarios": breached_scenarios,
        "reverse_stress_thresholds": {
            item.scenario: item.first_breaching_shock
            for item in request.reverse_stresses
        },
        "failures": failures,
        "decision": decision,
        "validation_environment": request.validation_environment,
        "historical_variance_only": False,
        "model_failure_included": True,
        "allocation_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    return dossier, decision


def register_assessment(
    db: Session, payload: RiskStressAssessmentCreate
) -> RiskStressAssessment:
    dossier, decision = build_dossier(payload)
    dossier_digest = record_digest(dossier)
    existing = db.scalar(
        select(RiskStressAssessment).where(
            or_(
                RiskStressAssessment.assessment_key == payload.assessment_key,
                RiskStressAssessment.dossier_digest == dossier_digest,
            )
        )
    )
    if existing:
        if existing.dossier_digest == dossier_digest:
            return existing
        raise RiskStressConflict(
            "Assessment key already exists with different evidence."
        )
    record = RiskStressAssessment(
        assessment_key=payload.assessment_key,
        candidate_digest=payload.request.candidate_digest,
        scenario_pack_digest=payload.request.scenario_pack_digest,
        request=payload.request.model_dump(mode="json"),
        dossier=dossier,
        dossier_digest=dossier_digest,
        decision=decision,
        assessed_by=payload.assessed_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise RiskStressConflict(
            "Assessment key or dossier digest already exists."
        ) from exc
    return record
