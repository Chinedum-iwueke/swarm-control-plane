import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.execution_event_schema import ExecutionEventSchemaRegistry
from app.models.microstructure_model import MicrostructureModelRegistry
from app.models.oms_schema import OmsSchemaRegistry
from app.models.portfolio_solver import PortfolioSolverRegistry
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.models.venue_identity import VenueIdentityRegistry
from app.schemas.quantitative_receipt import QuantitativeReceiptCreate


class QuantitativeReceiptConflict(RuntimeError):
    pass


PRODUCERS = {
    "ALPHA-001": "bt.institutional.alpha.real_data_admission_receipt",
    "DATA-001": "bt.institutional.data.reference_snapshot_receipt",
    "DATA-002": "bt.institutional.data.market_catalog_receipt",
    "DATA-003": "bt.institutional.data.lake_quality_receipt",
    "DISC-002": "bt.institutional.discovery.opportunity_map_receipt",
    "DISC-003": "bt.institutional.discovery.factor_program_receipt",
    "DISC-004": "bt.institutional.discovery.search_proposal_receipt",
    "DISC-005": "bt.institutional.discovery.symbolic_candidate_receipt",
    "DISC-007": "bt.institutional.discovery.selection_audit_receipt",
    "EXEC-001": "bt.institutional.execution.execution_journal_receipt",
    "EXEC-002": "bt.institutional.microstructure.microstructure_state_receipt",
    "EXEC-003": "bt.institutional.venue.venue_identity_receipt",
    "EXEC-004": "bt.institutional.oms.oms_reconciliation_receipt",
    "ML-002": "bt.institutional.ml.causal_materialization_receipt",
    "ML-003": "bt.institutional.ml.model_family_evaluation_receipt",
    "ML-004": "bt.institutional.ml.calibration_receipt",
    "PORT-002": "bt.institutional.portfolio.dependency_dossier_receipt",
    "PORT-003": "bt.institutional.construction.construction_dossier_receipt",
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
    if receipt["milestone"] == "PORT-003":
        solver_digest = receipt["result"].get("solver_digest")
        solver = db.scalar(
            select(PortfolioSolverRegistry).where(
                PortfolioSolverRegistry.specification_digest == solver_digest,
                PortfolioSolverRegistry.status == "active",
            )
        )
        if solver is None:
            raise QuantitativeReceiptConflict("PORT-003 solver is not active in the registry.")
    if receipt["milestone"] == "EXEC-001":
        schema_digest = receipt["result"].get("event_schema_digest")
        event_schema = db.scalar(
            select(ExecutionEventSchemaRegistry).where(
                ExecutionEventSchemaRegistry.specification_digest == schema_digest,
                ExecutionEventSchemaRegistry.status == "active",
            )
        )
        if event_schema is None:
            raise QuantitativeReceiptConflict("EXEC-001 event schema is not active in the registry.")
    if receipt["milestone"] == "EXEC-002":
        model_digest = receipt["result"].get("model_schema_digest")
        model = db.scalar(
            select(MicrostructureModelRegistry).where(
                MicrostructureModelRegistry.specification_digest == model_digest,
                MicrostructureModelRegistry.status == "active",
            )
        )
        if model is None:
            raise QuantitativeReceiptConflict("EXEC-002 model is not active in the registry.")
    if receipt["milestone"] == "EXEC-003":
        mapping_digest = receipt["result"].get("mapping_schema_digest")
        mapping = db.scalar(
            select(VenueIdentityRegistry).where(
                VenueIdentityRegistry.specification_digest == mapping_digest,
                VenueIdentityRegistry.status == "active",
            )
        )
        if mapping is None:
            raise QuantitativeReceiptConflict(
                "EXEC-003 venue identity schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-004":
        schema_digest = receipt["result"].get("oms_schema_digest")
        schema = db.scalar(
            select(OmsSchemaRegistry).where(
                OmsSchemaRegistry.specification_digest == schema_digest,
                OmsSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-004 OMS schema is not active in the registry."
            )
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
