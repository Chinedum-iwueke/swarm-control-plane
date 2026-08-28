from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.reference_data import ReferenceDataSnapshot
from app.models.risk_rules import RiskRuleEvaluation
from app.models.risk_stress import RiskStressAssessment
from app.schemas.reference_data import PointInTimeReferenceSnapshot
from app.schemas.risk_rules import RiskRuleEvaluationCreate
from app.services.research import record_digest


class RiskRuleConflict(RuntimeError):
    pass


def _multiple(value: Decimal, increment: Decimal) -> bool:
    return value % increment == 0


def build_receipt(
    payload: RiskRuleEvaluationCreate, reference, stress
) -> tuple[dict, str]:
    request = payload.request
    pack = request.rule_pack
    position = request.position
    if record_digest(request) != payload.request_digest:
        raise RiskRuleConflict("Risk rule request digest does not match content.")
    if record_digest(pack) != request.rule_pack_digest:
        raise RiskRuleConflict("Rule pack digest does not match content.")
    if reference.snapshot_digest != request.reference_snapshot_digest:
        raise RiskRuleConflict("DATA-001 snapshot digest does not match.")
    if (
        stress.dossier_digest != request.risk_stress_dossier_digest
        or stress.decision != "admissible"
    ):
        raise RiskRuleConflict("A current admissible RISK-001 dossier is required.")
    snapshot = PointInTimeReferenceSnapshot.model_validate(reference.snapshot)
    listings = [
        item for item in snapshot.listings if item.listing_id == pack.listing_id
    ]
    if (
        len(listings) != 1
        or listings[0].instrument_id != pack.instrument_id
        or listings[0].venue_id != pack.venue_id
    ):
        raise RiskRuleConflict("Rule pack identity does not match DATA-001.")
    failures: list[str] = []
    if pack.available_at > request.evaluated_at:
        failures.append("rule_not_yet_known")
    if request.evaluated_at < pack.effective_from or (
        pack.effective_to and request.evaluated_at >= pack.effective_to
    ):
        failures.append("rule_not_effective")
    age = int((request.evaluated_at - pack.available_at).total_seconds())
    if age > request.maximum_rule_age_seconds:
        failures.append("stale_rule_pack")
    if pack.status != "active":
        failures.append("rule_pack_not_active")
    notional = position.quantity * position.mark_price
    tiers = sorted(pack.margin_tiers, key=lambda item: item.notional_floor)
    tier = next(
        (item for item in tiers if item.notional_floor <= notional < item.notional_cap),
        None,
    )
    if tier is None:
        failures.append("notional_outside_margin_tiers")
        tier = tiers[-1]
    if position.requested_leverage > tier.maximum_leverage:
        failures.append("leverage_limit_breached")
    if not _multiple(position.quantity, pack.quantity_increment):
        failures.append("quantity_increment_violation")
    if not _multiple(position.entry_price, pack.price_increment):
        failures.append("price_increment_violation")
    mark_deviation = (
        abs(position.mark_price - position.index_price) / position.index_price
    )
    if mark_deviation > pack.maximum_mark_deviation:
        failures.append("mark_price_deviation_breached")
    funding_rate = abs(position.accrued_funding) / notional
    if funding_rate > pack.maximum_abs_funding_rate:
        failures.append("funding_limit_breached")
    direction = Decimal(1) if position.side == "long" else Decimal(-1)
    unrealized_pnl = (
        direction * position.quantity * (position.mark_price - position.entry_price)
    )
    equity = (
        position.collateral
        + unrealized_pnl
        - position.accrued_funding
        - position.fee_reserve
    )
    maintenance_margin = max(
        Decimal(0), notional * tier.maintenance_margin_rate - tier.maintenance_amount
    )
    liquidation_buffer = equity - maintenance_margin
    if liquidation_buffer < pack.minimum_liquidation_buffer:
        failures.append("liquidation_buffer_breached")
    decision = "allowed" if not failures else "denied"
    receipt = {
        "schema_version": "risk-rule-evaluation-receipt-v1.0.0",
        "reference_snapshot_digest": reference.snapshot_digest,
        "risk_stress_dossier_digest": stress.dossier_digest,
        "rule_pack_digest": request.rule_pack_digest,
        "position_state_digest": position.state_digest,
        "venue_id": pack.venue_id,
        "instrument_id": pack.instrument_id,
        "listing_id": pack.listing_id,
        "rule_version": pack.version,
        "rule_status": pack.status,
        "rule_age_seconds": age,
        "selected_margin_tier": tier.tier,
        "notional": str(notional),
        "initial_margin_required": str(notional / position.requested_leverage),
        "maintenance_margin": str(maintenance_margin),
        "equity_after_funding_and_fees": str(equity),
        "liquidation_buffer": str(liquidation_buffer),
        "mark_deviation": str(mark_deviation),
        "effective_funding_rate": str(funding_rate),
        "failures": failures,
        "decision": decision,
        "allocation_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    return receipt, decision


def register_evaluation(
    db: Session, payload: RiskRuleEvaluationCreate
) -> RiskRuleEvaluation:
    reference = db.get(ReferenceDataSnapshot, payload.request.reference_snapshot_id)
    stress = db.get(RiskStressAssessment, payload.request.risk_stress_assessment_id)
    if reference is None or stress is None:
        raise RiskRuleConflict("DATA-001 and RISK-001 dependencies are required.")
    receipt, decision = build_receipt(payload, reference, stress)
    receipt_digest = record_digest(receipt)
    existing = db.scalar(
        select(RiskRuleEvaluation).where(
            or_(
                RiskRuleEvaluation.evaluation_key == payload.evaluation_key,
                RiskRuleEvaluation.receipt_digest == receipt_digest,
            )
        )
    )
    if existing:
        if existing.receipt_digest == receipt_digest:
            return existing
        raise RiskRuleConflict("Evaluation key already exists with different evidence.")
    record = RiskRuleEvaluation(
        evaluation_key=payload.evaluation_key,
        reference_snapshot_id=payload.request.reference_snapshot_id,
        risk_stress_assessment_id=payload.request.risk_stress_assessment_id,
        rule_pack_digest=payload.request.rule_pack_digest,
        request_digest=payload.request_digest,
        request=payload.request.model_dump(mode="json"),
        receipt=receipt,
        receipt_digest=receipt_digest,
        decision=decision,
        evaluated_by=payload.evaluated_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise RiskRuleConflict(
            "Evaluation key or receipt digest already exists."
        ) from exc
    return record
