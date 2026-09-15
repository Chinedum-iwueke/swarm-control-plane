import hashlib
import json
from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.adapter_certification_schema import AdapterCertificationSchemaRegistry
from app.models.candidate_admission_schema import CandidateAdmissionSchemaRegistry
from app.models.demo_certification_schema import DemoCertificationSchemaRegistry
from app.models.execution_calibration_schema import ExecutionCalibrationSchemaRegistry
from app.models.execution_degradation_schema import ExecutionDegradationSchemaRegistry
from app.models.execution_event_schema import ExecutionEventSchemaRegistry
from app.models.execution_safety_schema import ExecutionSafetySchemaRegistry
from app.models.execution_schedule_schema import ExecutionScheduleSchemaRegistry
from app.models.execution_telemetry import ExecutionTelemetrySchemaRegistry
from app.models.microstructure_model import MicrostructureModelRegistry
from app.models.oms_schema import OmsSchemaRegistry
from app.models.portfolio_capacity_schema import PortfolioCapacitySchemaRegistry
from app.models.portfolio_solver import PortfolioSolverRegistry
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.models.realtime_risk_schema import RealtimeRiskSchemaRegistry
from app.models.risk_budget_schema import RiskBudgetSchemaRegistry
from app.models.shadow_monitoring_schema import ShadowMonitoringSchemaRegistry
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
    "DEMO-001": "bt.institutional.demo_certification.demo_certification_receipt",
    "EXEC-001": "bt.institutional.execution.execution_journal_receipt",
    "EXEC-002": "bt.institutional.microstructure.microstructure_state_receipt",
    "EXEC-003": "bt.institutional.venue.venue_identity_receipt",
    "EXEC-004": "bt.institutional.oms.oms_reconciliation_receipt",
    "EXEC-005": "bt.institutional.execution_calibration.execution_calibration_receipt",
    "EXEC-006": "bt.institutional.execution_scheduler.execution_schedule_receipt",
    "EXEC-007": "bt.institutional.runtime_safety.runtime_safety_receipt",
    "EXEC-008": "bt.institutional.adapter_certification.adapter_certification_receipt",
    "EXEC-009": "bt.institutional.execution_degradation.execution_degradation_receipt",
    "EXEC-011": "bt.institutional.venue_telemetry.venue_telemetry_receipt",
    "ML-002": "bt.institutional.ml.causal_materialization_receipt",
    "ML-003": "bt.institutional.ml.model_family_evaluation_receipt",
    "ML-004": "bt.institutional.ml.calibration_receipt",
    "PORT-002": "bt.institutional.portfolio.dependency_dossier_receipt",
    "PORT-003": "bt.institutional.construction.construction_dossier_receipt",
    "PORT-004": "bt.institutional.capacity.capacity_dossier_receipt",
    "RL-001": "bt.institutional.rl.offline_dataset_receipt",
    "RL-002": "bt.institutional.rl.off_policy_evaluation_receipt",
    "RISK-001": "bt.institutional.risk.stress_dossier_receipt",
    "RISK-002": "bt.institutional.risk.venue_rule_receipt",
    "RISK-003": "bt.institutional.risk_budget.dynamic_risk_budget_receipt",
    "SHADOW-002": "bt.institutional.shadow_monitoring.shadow_monitoring_receipt",
    "RISK-004": "bt.institutional.candidate_admission.candidate_admission_receipt",
    "RISK-005": "bt.institutional.realtime_risk.realtime_risk_decision_receipt",
}


def _digest(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _validate_inventory_root(db: Session, receipt: dict) -> None:
    result = receipt["result"]
    shards = result.get("shards")
    if not isinstance(shards, list) or not shards or len(shards) > 10000:
        raise QuantitativeReceiptConflict("Complete inventory requires bounded registered shards.")
    if (result.get("shard_count") != len(shards) or not isinstance(result.get("run_id"), str)
            or not isinstance(result.get("claim_boundary"), str) or not result["claim_boundary"]):
        raise QuantitativeReceiptConflict("Malformed inventory root binding.")
    if receipt["dataset_digest"] != _digest([item.get("dataset_digest") for item in shards if isinstance(item, dict)]) or receipt["input_digest"] != _digest(shards):
        raise QuantitativeReceiptConflict("Inventory root descriptors are not content-bound.")
    counts, assets = Counter(), set()
    previous_path = None
    total = 0
    for index, descriptor in enumerate(shards):
        if not isinstance(descriptor, dict) or descriptor.get("shard_index") != index:
            raise QuantitativeReceiptConflict("Inventory shard indices must be contiguous.")
        record = db.scalar(select(QuantitativeProducerReceipt).where(
            QuantitativeProducerReceipt.receipt_digest == descriptor.get("receipt_digest"),
            QuantitativeProducerReceipt.producer == "bt.institutional.lake_inventory.lake_inventory_shard_receipt",
            QuantitativeProducerReceipt.source_commit == receipt["source_commit"],
        ))
        if record is None:
            raise QuantitativeReceiptConflict("Inventory shard is not registered under the bound source.")
        shard = record.receipt["result"]
        if (shard.get("run_id") != result["run_id"] or shard.get("shard_index") != index
                or shard.get("object_count") != descriptor.get("object_count")
                or record.dataset_digest != descriptor.get("dataset_digest")):
            raise QuantitativeReceiptConflict("Inventory shard conflicts with its root binding.")
        paths = [item["partition_id"] for item in shard["objects"]]
        if paths != sorted(paths) or (previous_path is not None and paths[0] <= previous_path):
            raise QuantitativeReceiptConflict("Inventory shard paths overlap or are not globally ordered.")
        previous_path = paths[-1]
        counts.update(shard["dispositions"])
        assets.update(tuple(identity) for identity in shard["assets"])
        total += shard["object_count"]
    if (result.get("object_count") != total or result.get("dispositions") != dict(counts)
            or result.get("assets") != [list(identity) for identity in sorted(assets)]):
        raise QuantitativeReceiptConflict("Inventory root summaries do not match registered shards.")
    if result.get("group_labels_are_optional_metadata") is not True:
        raise QuantitativeReceiptConflict("Inventory group labels cannot become mandatory universes.")


def _validate_full_lake_quality(db: Session, receipt: dict) -> None:
    result = receipt["result"]
    objects = result.get("objects")
    skipped = result.get("unprocessed_dispositions")
    if (result.get("schema_version") != "data003-full-lake-quality-v1.0.0"
            or not isinstance(objects, list) or len(objects) > 10000
            or result.get("object_count") != len(objects)
            or not isinstance(skipped, dict)
            or any(type(count) is not int or count < 0 for count in skipped.values())
            or not isinstance(result.get("claim_boundary"), str)):
        raise QuantitativeReceiptConflict("Malformed bounded full-lake quality receipt.")
    try:
        start = datetime.fromisoformat(result["window_start"])
        end = datetime.fromisoformat(result["window_end"])
        if start.utcoffset() is None or end.utcoffset() is None or end <= start:
            raise ValueError("invalid window")
    except (KeyError, TypeError, ValueError) as error:
        raise QuantitativeReceiptConflict("Quality window clocks must be aware and ordered.") from error
    inventory = db.scalar(select(QuantitativeProducerReceipt).where(
        QuantitativeProducerReceipt.receipt_digest == result.get("inventory_receipt_digest"),
        QuantitativeProducerReceipt.producer == "bt.institutional.lake_inventory.full_lake_inventory_receipt",
    ))
    if inventory is None or inventory.dataset_digest != receipt["dataset_digest"]:
        raise QuantitativeReceiptConflict("Quality requires the complete bound registered inventory.")
    if (result.get("inventoried_object_count") != inventory.receipt["result"]["object_count"]
            or len(objects) + sum(skipped.values()) != result["inventoried_object_count"]):
        raise QuantitativeReceiptConflict("Quality accounting does not cover its inventory.")
    requested = {}
    checks_required = {
        "nonempty_window", "complete_window_grid", "strict_timestamp_order",
        "no_internal_gaps", "aligned_timestamps", "no_null_timestamps",
        "required_fields_nonnull", "path_exchange_symbol_consistent", "valid_ohlcv",
    }
    for item in objects:
        if not isinstance(item, dict) or not isinstance(item.get("partition_id"), str):
            raise QuantitativeReceiptConflict("Quality object identity is required.")
        if item["partition_id"] in requested or item.get("execution_eligible") is not False:
            raise QuantitativeReceiptConflict("Quality cannot duplicate objects or infer execution admission.")
        passed = item.get("panel_quality_passed")
        if (type(passed) is not bool
                or item.get("disposition") != ("panel_quality_passed" if passed else "quarantined")
                or not isinstance(item.get("reason_codes"), list)
                or (not passed and not item["reason_codes"])):
            raise QuantitativeReceiptConflict("Quality classification contradicts its pass status.")
        if item.get("panel_quality_passed") is True and (
            not isinstance(item.get("checks"), dict) or set(item["checks"]) != checks_required
            or any(value is not True for value in item["checks"].values())
            or item.get("reason_codes") != []
        ):
            raise QuantitativeReceiptConflict("Passing quality contradicts its checks.")
        requested[item["partition_id"]] = item
    if result.get("dispositions") != dict(Counter(item["disposition"] for item in objects)):
        raise QuantitativeReceiptConflict("Quality disposition summary does not match its objects.")

    def source_objects():
        root = inventory.receipt["result"]
        if "objects" in root:
            yield from root["objects"]
        else:
            for descriptor in root["shards"]:
                record = db.scalar(select(QuantitativeProducerReceipt).where(
                    QuantitativeProducerReceipt.receipt_digest == descriptor["receipt_digest"]))
                if record is None:
                    raise QuantitativeReceiptConflict("Bound inventory lost shard custody.")
                yield from record.receipt["result"]["objects"]

    remaining = set(requested)
    for source in source_objects():
        if not remaining:
            break
        key = source["partition_id"]
        if key not in remaining:
            continue
        item = requested[key]
        if (source.get("layer") != "canonical" or source.get("dataset") != "research_panel"
                or source.get("disposition") != "cataloged_pending_quality"
                or any(item.get(field) != source.get(field) for field in
                       ("content_digest", "market", "venue", "instrument", "timeframe"))):
            raise QuantitativeReceiptConflict("Quality object conflicts with its source inventory.")
        remaining.remove(key)
    if remaining:
        raise QuantitativeReceiptConflict("Quality includes objects absent from the inventory.")


def register_receipt(
    db: Session, payload: QuantitativeReceiptCreate
) -> QuantitativeProducerReceipt:
    receipt = payload.receipt.model_dump(mode="json")
    receipt_digest = receipt.pop("receipt_digest")
    inventory_producer = "bt.institutional.lake_inventory.full_lake_inventory_receipt"
    is_inventory = receipt["producer"] == inventory_producer
    is_inventory_shard = receipt["producer"] == "bt.institutional.lake_inventory.lake_inventory_shard_receipt"
    is_full_quality = receipt["producer"] == "bt.institutional.lake_quality.full_lake_quality_receipt"
    if PRODUCERS[receipt["milestone"]] != receipt["producer"] and not (
        receipt["milestone"] == "DATA-002" and (is_inventory or is_inventory_shard)
        or receipt["milestone"] == "DATA-003" and is_full_quality
    ):
        raise QuantitativeReceiptConflict(
            "Producer is not authoritative for the declared milestone."
        )
    if _digest(receipt["result"]) != receipt["result_digest"]:
        raise QuantitativeReceiptConflict("Result digest does not match content.")
    if _digest(receipt) != receipt_digest:
        raise QuantitativeReceiptConflict("Producer receipt digest does not match.")
    if is_full_quality:
        _validate_full_lake_quality(db, receipt)
    if is_inventory and receipt["result"].get("schema_version") == "data002-full-lake-inventory-v2.0.0":
        _validate_inventory_root(db, receipt)
    elif is_inventory or is_inventory_shard:
        result = receipt["result"]
        objects = result.get("objects")
        if (
            result.get("schema_version") != ("data002-lake-inventory-shard-v1.0.0" if is_inventory_shard else "data002-full-lake-inventory-v1.0.0")
            or not isinstance(objects, list)
            or len(objects) > 250_000
            or result.get("object_count") != len(objects)
            or any(not isinstance(item, dict) for item in objects)
            or not isinstance(result.get("assets"), list)
            or not isinstance(result.get("dispositions"), dict)
            or not isinstance(result.get("claim_boundary"), str)
        ):
            raise QuantitativeReceiptConflict("Malformed full-lake inventory.")
        if is_inventory_shard and (not objects or len(objects) > 10000
                                   or not isinstance(result.get("run_id"), str)
                                   or not result["run_id"]
                                   or type(result.get("shard_index")) is not int
                                   or result["shard_index"] < 0):
            raise QuantitativeReceiptConflict("Malformed bounded inventory shard.")
        counts = result["dispositions"]
        if any(not isinstance(count, int) or count < 0 for count in counts.values()) or sum(counts.values()) != len(objects):
            raise QuantitativeReceiptConflict("Inventory disposition counts do not match.")
        if any(item.get("disposition") not in ("quarantined", "cataloged_pending_quality") for item in objects):
            raise QuantitativeReceiptConflict("Unknown inventory disposition.")
        if counts != dict(Counter(item.get("disposition") for item in objects)):
            raise QuantitativeReceiptConflict("Inventory classifications do not match its objects.")
        assets = set()
        for item in objects:
            if "instrument" in item:
                identity = tuple(item.get(key) for key in ("market", "venue", "instrument"))
                if any(not isinstance(value, str) or not value for value in identity):
                    raise QuantitativeReceiptConflict("Malformed inventory asset identity.")
                assets.add(identity)
            if item.get("disposition") == "cataloged_pending_quality":
                content_digest = item.get("content_digest")
                if (
                    not isinstance(content_digest, str)
                    or len(content_digest) != 64
                    or any(char not in "0123456789abcdef" for char in content_digest)
                    or not isinstance(item.get("output_columns"), list)
                    or not isinstance(item.get("row_count"), int)
                    or item["row_count"] < 0
                ):
                    raise QuantitativeReceiptConflict("Cataloged inventory object lacks content/schema metadata.")
        if result["assets"] != [list(identity) for identity in sorted(assets)]:
            raise QuantitativeReceiptConflict("Inventory asset summary does not match its objects.")
        identities = [item.get("partition_id") for item in objects]
        if any(not isinstance(key, str) or not key for key in identities):
            raise QuantitativeReceiptConflict("Inventory object identity is required.")
        if len(set(identities)) != len(identities):
            raise QuantitativeReceiptConflict("Duplicate inventory object identity.")
        if any(
            item.get("execution_eligible") is not False
            or item.get("disposition") not in {"quarantined", "cataloged_pending_quality"}
            for item in objects
        ):
            raise QuantitativeReceiptConflict("Inventory cannot infer execution admission.")
        if receipt["dataset_digest"] != _digest(objects) or receipt["input_digest"] != _digest(objects):
            raise QuantitativeReceiptConflict("Inventory objects are not content-bound.")
    if receipt["milestone"] == "PORT-003":
        solver_digest = receipt["result"].get("solver_digest")
        solver = db.scalar(
            select(PortfolioSolverRegistry).where(
                PortfolioSolverRegistry.specification_digest == solver_digest,
                PortfolioSolverRegistry.status == "active",
            )
        )
        if solver is None:
            raise QuantitativeReceiptConflict(
                "PORT-003 solver is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-001":
        schema_digest = receipt["result"].get("event_schema_digest")
        event_schema = db.scalar(
            select(ExecutionEventSchemaRegistry).where(
                ExecutionEventSchemaRegistry.specification_digest == schema_digest,
                ExecutionEventSchemaRegistry.status == "active",
            )
        )
        if event_schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-001 event schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-002":
        model_digest = receipt["result"].get("model_schema_digest")
        model = db.scalar(
            select(MicrostructureModelRegistry).where(
                MicrostructureModelRegistry.specification_digest == model_digest,
                MicrostructureModelRegistry.status == "active",
            )
        )
        if model is None:
            raise QuantitativeReceiptConflict(
                "EXEC-002 model is not active in the registry."
            )
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
    if receipt["milestone"] == "EXEC-005":
        schema_digest = receipt["result"].get("calibration_schema_digest")
        schema = db.scalar(
            select(ExecutionCalibrationSchemaRegistry).where(
                ExecutionCalibrationSchemaRegistry.specification_digest
                == schema_digest,
                ExecutionCalibrationSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-005 execution-calibration schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-009":
        schema_digest = receipt["result"].get("degradation_schema_digest")
        schema = db.scalar(
            select(ExecutionDegradationSchemaRegistry).where(
                ExecutionDegradationSchemaRegistry.specification_digest
                == schema_digest,
                ExecutionDegradationSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-009 execution-degradation schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-011":
        schema_digest = receipt["result"].get("telemetry_schema_digest")
        schema = db.scalar(
            select(ExecutionTelemetrySchemaRegistry).where(
                ExecutionTelemetrySchemaRegistry.specification_digest == schema_digest,
                ExecutionTelemetrySchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-011 execution-telemetry schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-006":
        schema_digest = receipt["result"].get("execution_schedule_schema_digest")
        schema = db.scalar(
            select(ExecutionScheduleSchemaRegistry).where(
                ExecutionScheduleSchemaRegistry.specification_digest == schema_digest,
                ExecutionScheduleSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-006 execution-schedule schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-007":
        schema_digest = receipt["result"].get("runtime_safety_schema_digest")
        schema = db.scalar(
            select(ExecutionSafetySchemaRegistry).where(
                ExecutionSafetySchemaRegistry.specification_digest == schema_digest,
                ExecutionSafetySchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-007 execution-safety schema is not active in the registry."
            )
    if receipt["milestone"] == "EXEC-008":
        schema_digest = receipt["result"].get("adapter_certification_schema_digest")
        schema = db.scalar(
            select(AdapterCertificationSchemaRegistry).where(
                AdapterCertificationSchemaRegistry.specification_digest
                == schema_digest,
                AdapterCertificationSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "EXEC-008 adapter-certification schema is not active in the registry."
            )
    if receipt["milestone"] == "DEMO-001":
        schema_digest = receipt["result"].get("demo_certification_schema_digest")
        schema = db.scalar(
            select(DemoCertificationSchemaRegistry).where(
                DemoCertificationSchemaRegistry.specification_digest == schema_digest,
                DemoCertificationSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "DEMO-001 demo-certification schema is not active in the registry."
            )
    if receipt["milestone"] == "PORT-004":
        schema_digest = receipt["result"].get("capacity_schema_digest")
        schema = db.scalar(
            select(PortfolioCapacitySchemaRegistry).where(
                PortfolioCapacitySchemaRegistry.specification_digest == schema_digest,
                PortfolioCapacitySchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "PORT-004 portfolio-capacity schema is not active in the registry."
            )
    if receipt["milestone"] == "RISK-003":
        schema_digest = receipt["result"].get("risk_budget_schema_digest")
        schema = db.scalar(
            select(RiskBudgetSchemaRegistry).where(
                RiskBudgetSchemaRegistry.specification_digest == schema_digest,
                RiskBudgetSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "RISK-003 risk-budget schema is not active in the registry."
            )
    if receipt["milestone"] == "SHADOW-002":
        schema_digest = receipt["result"].get("shadow_monitoring_schema_digest")
        schema = db.scalar(
            select(ShadowMonitoringSchemaRegistry).where(
                ShadowMonitoringSchemaRegistry.specification_digest == schema_digest,
                ShadowMonitoringSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "SHADOW-002 monitoring schema is not active in the registry."
            )
    if receipt["milestone"] == "RISK-004":
        schema_digest = receipt["result"].get("admission_schema_digest")
        schema = db.scalar(
            select(CandidateAdmissionSchemaRegistry).where(
                CandidateAdmissionSchemaRegistry.specification_digest == schema_digest,
                CandidateAdmissionSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "RISK-004 admission schema is not active in the registry."
            )
    if receipt["milestone"] == "RISK-005":
        schema_digest = receipt["result"].get("realtime_risk_schema_digest")
        schema = db.scalar(
            select(RealtimeRiskSchemaRegistry).where(
                RealtimeRiskSchemaRegistry.specification_digest == schema_digest,
                RealtimeRiskSchemaRegistry.status == "active",
            )
        )
        if schema is None:
            raise QuantitativeReceiptConflict(
                "RISK-005 real-time risk schema is not active in the registry."
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
