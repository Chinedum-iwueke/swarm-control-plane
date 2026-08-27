from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.falsification import MechanismEvaluation
from app.models.selection_audit import SelectionBiasAudit
from app.schemas.selection_audit import SelectionBiasAuditCreate
from app.services.research import record_digest


class SelectionAuditConflict(RuntimeError):
    pass


def register_selection_audit(
    db: Session, payload: SelectionBiasAuditCreate
) -> SelectionBiasAudit:
    if record_digest(payload.ledger) != payload.ledger_digest:
        raise SelectionAuditConflict("Ledger digest does not match canonical content.")
    mechanism = db.get(MechanismEvaluation, payload.mechanism_evaluation_id)
    if mechanism is None:
        raise SelectionAuditConflict("A retained mechanism evaluation is required.")
    ledger = payload.ledger
    completed = [item for item in ledger.trials if item.status == "completed"]
    if not completed:
        raise SelectionAuditConflict("The complete family has no completed trials.")
    if payload.correction_policy.effective_trial_count != ledger.planned_trial_count:
        raise SelectionAuditConflict(
            "Multiplicity correction must cover the complete registered family."
        )
    if payload.correction_policy.alpha > 0.05:
        raise SelectionAuditConflict("Audit alpha cannot exceed institutional policy.")
    if payload.correction_policy.maximum_pbo > 0.5:
        raise SelectionAuditConflict("PBO boundary cannot exceed institutional policy.")
    if any(
        split.candidate_count != ledger.planned_trial_count
        for split in ledger.validation_splits
    ):
        raise SelectionAuditConflict(
            "Validation splits must rank the complete registered family."
        )

    winner = next(
        item for item in completed if item.trial_key == ledger.reported_winner_trial_key
    )
    p_values = sorted(item.p_value for item in completed if item.p_value is not None)
    multiplicity = payload.correction_policy.effective_trial_count
    family_wise_p = min(1.0, min(p_values) * multiplicity)
    discoveries = max(
        (
            rank
            for rank, value in enumerate(p_values, start=1)
            if value <= payload.correction_policy.alpha * rank / multiplicity
        ),
        default=0,
    )
    assert winner.sharpe is not None and winner.sharpe_standard_error is not None
    selection_penalty = math.sqrt(2 * math.log(max(1, multiplicity)))
    adjusted_sharpe = winner.sharpe - selection_penalty * winner.sharpe_standard_error
    pbo = sum(
        split.winner_rank > math.ceil(split.candidate_count / 2)
        for split in ledger.validation_splits
    ) / len(ledger.validation_splits)
    undeclared = sorted(
        set(ledger.observed_research_operations)
        - set(ledger.declared_researcher_degrees)
    )
    optional_stopping = (
        ledger.stopping.outcome_access_before_stop
        or ledger.stopping.stop_reason == "outcome_triggered"
    )
    process_blocks = []
    if optional_stopping:
        process_blocks.append("optional_stopping")
    if undeclared:
        process_blocks.append("undeclared_researcher_degrees")
    if process_blocks:
        conclusion = "blocked"
    elif (
        family_wise_p <= payload.correction_policy.alpha
        and discoveries > 0
        and adjusted_sharpe > 0
        and pbo <= payload.correction_policy.maximum_pbo
    ):
        conclusion = "selection_adjusted"
    else:
        conclusion = "selection_risk_detected"
    audit = {
        "schema_version": "selection-bias-audit-v1.0.0",
        "mechanism_evaluation_id": str(mechanism.id),
        "ledger_digest": payload.ledger_digest,
        "correction_policy": payload.correction_policy.model_dump(mode="json"),
        "complete_family": True,
        "planned_trials": ledger.planned_trial_count,
        "completed_trials": len(completed),
        "failed_trials": sum(item.status == "failed" for item in ledger.trials),
        "cancelled_trials": sum(item.status == "cancelled" for item in ledger.trials),
        "family_wise_p": round(family_wise_p, 12),
        "benjamini_hochberg_discoveries": discoveries,
        "selection_adjusted_sharpe": round(adjusted_sharpe, 12),
        "deflated_sharpe_diagnostic": round(adjusted_sharpe, 12),
        "probability_of_backtest_overfitting": round(pbo, 12),
        "optional_stopping": optional_stopping,
        "undeclared_researcher_degrees": undeclared,
        "process_blocks": process_blocks,
        "promotion_authority": False,
    }
    audit_digest = record_digest(audit)
    prior = None
    if payload.supersedes_audit_id:
        prior = db.scalar(
            select(SelectionBiasAudit)
            .where(SelectionBiasAudit.id == payload.supersedes_audit_id)
            .with_for_update()
        )
        if (
            prior is None
            or prior.status != "active"
            or prior.mechanism_evaluation_id != mechanism.id
        ):
            raise SelectionAuditConflict("Superseded audit is absent or inactive.")
        prior.status = "superseded"
    record = SelectionBiasAudit(
        audit_key=payload.audit_key,
        mechanism_evaluation_id=mechanism.id,
        ledger=ledger.model_dump(mode="json"),
        ledger_digest=payload.ledger_digest,
        audit=audit,
        conclusion=conclusion,
        audit_digest=audit_digest,
        supersedes_audit_id=payload.supersedes_audit_id,
        status="active",
        audited_by=payload.audited_by,
    )
    db.add(record)
    db.flush()
    return record
