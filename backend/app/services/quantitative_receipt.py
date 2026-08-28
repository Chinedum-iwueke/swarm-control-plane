import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.schemas.quantitative_receipt import QuantitativeReceiptCreate


class QuantitativeReceiptConflict(RuntimeError):
    pass


PRODUCERS = {
    "DATA-001": "bt.institutional.data.reference_snapshot_receipt",
    "DATA-002": "bt.institutional.data.market_catalog_receipt",
    "DATA-003": "bt.institutional.data.lake_quality_receipt",
    "DISC-002": "bt.institutional.discovery.opportunity_map_receipt",
    "DISC-003": "bt.institutional.discovery.factor_program_receipt",
    "DISC-004": "bt.institutional.discovery.search_proposal_receipt",
    "DISC-005": "bt.institutional.discovery.symbolic_candidate_receipt",
    "DISC-007": "bt.institutional.discovery.selection_audit_receipt",
    "ML-002": "bt.institutional.ml.causal_materialization_receipt",
    "ML-003": "bt.institutional.ml.model_family_evaluation_receipt",
    "ML-004": "bt.institutional.ml.calibration_receipt",
    "PORT-002": "bt.institutional.portfolio.dependency_dossier_receipt",
    "RL-001": "bt.institutional.rl.offline_dataset_receipt",
    "RL-002": "bt.institutional.rl.off_policy_evaluation_receipt",
    "RISK-001": "bt.institutional.risk.stress_dossier_receipt",
    "RISK-002": "bt.institutional.risk.venue_rule_receipt",
}


def _digest(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def register_receipt(
    db: Session, payload: QuantitativeReceiptCreate
) -> QuantitativeProducerReceipt:
    receipt = payload.receipt.model_dump(mode="json")
    receipt_digest = receipt.pop("receipt_digest")
    if PRODUCERS[receipt["milestone"]] != receipt["producer"]:
        raise QuantitativeReceiptConflict(
            "Producer is not authoritative for the declared milestone."
        )
    if _digest(receipt["result"]) != receipt["result_digest"]:
        raise QuantitativeReceiptConflict("Result digest does not match content.")
    if _digest(receipt) != receipt_digest:
        raise QuantitativeReceiptConflict("Producer receipt digest does not match.")
    receipt["receipt_digest"] = receipt_digest
    existing = db.scalar(
        select(QuantitativeProducerReceipt).where(
            QuantitativeProducerReceipt.receipt_digest == receipt_digest
        )
    )
    if existing:
        return existing
    record = QuantitativeProducerReceipt(
        milestone=receipt["milestone"],
        producer=receipt["producer"],
        producer_version=receipt["producer_version"],
        source_commit=receipt["source_commit"],
        dataset_digest=receipt["dataset_digest"],
        result_digest=receipt["result_digest"],
        receipt_digest=receipt_digest,
        receipt=receipt,
        registered_by=payload.registered_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise QuantitativeReceiptConflict("Receipt digest already exists.") from exc
    return record
