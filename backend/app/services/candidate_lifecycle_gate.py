from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quantitative_receipt import QuantitativeProducerReceipt


def require_risk004_evidence(
    db: Session,
    *,
    subject_type: str,
    subject_digest: str,
    requested_action: str,
    evidence: list[str],
) -> None:
    """Require a fresh, exact RISK-004 recommendation for candidate transitions."""
    if subject_type != "portfolio-candidate":
        return
    records = db.scalars(
        select(QuantitativeProducerReceipt).where(
            QuantitativeProducerReceipt.milestone == "RISK-004",
            QuantitativeProducerReceipt.receipt_digest.in_(evidence),
        )
    ).all()
    matches = []
    now = datetime.now(UTC)
    for record in records:
        result = record.receipt.get("result", {})
        expires_at = datetime.fromisoformat(
            str(result.get("expires_at", "")).replace("Z", "+00:00")
        )
        if (
            result.get("candidate_digest") == subject_digest
            and result.get("requested_action") == requested_action
            and result.get("eligible_for_authority_review") is True
            and expires_at > now
        ):
            matches.append(record)
    if len(matches) != 1:
        raise HTTPException(
            status_code=409,
            detail="Candidate lifecycle transition requires one fresh, exact RISK-004 receipt.",
        )
