from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.data_contract import ResearchDatasetBuild
from app.models.offline_rl import OfflineRLDatasetContract
from app.schemas.offline_rl import OfflineRLDatasetCreate
from app.services.research import record_digest


class OfflineRLConflict(RuntimeError):
    pass


def build_audit(
    payload: OfflineRLDatasetCreate, build: ResearchDatasetBuild
) -> tuple[dict, str]:
    contract = payload.contract
    if record_digest(contract) != payload.contract_digest:
        raise OfflineRLConflict("Offline-RL contract digest does not match content.")
    summary = contract.audit_summary
    policy = contract.evaluation
    failures: list[str] = []
    if build.content_digest != build.rebuild_content_digest:
        failures.append("dataset_rebuild_mismatch")
    if any(not item.get("passed", False) for item in build.quality_results):
        failures.append("dataset_quality_failed")
    if summary.transition_count > build.rows:
        failures.append("transition_count_exceeds_dataset")
    if summary.terminal_transition_count > summary.transition_count:
        failures.append("terminal_count_exceeds_transitions")
    temporal_violations = (
        summary.duplicate_transition_count
        + summary.out_of_order_transition_count
        + summary.state_availability_violation_count
        + summary.reward_availability_violation_count
    )
    if temporal_violations:
        failures.append("temporal_or_leakage_violation")
    if summary.missing_propensity_count:
        failures.append("missing_behavior_propensity")
    support_failures = []
    for item in summary.action_support:
        reasons = []
        if item.observations < policy.minimum_action_support:
            reasons.append("insufficient_observations")
        if (
            item.minimum_propensity
            < contract.behavior_policy.minimum_allowed_propensity
        ):
            reasons.append("propensity_below_floor")
        if item.maximum_importance_weight > policy.maximum_importance_weight:
            reasons.append("importance_weight_exceeds_cap")
        if reasons:
            support_failures.append({"action_key": item.action_key, "reasons": reasons})
    if support_failures:
        failures.append("action_support_gap")
    limitations = [
        {
            "confounder_key": item.confounder_key,
            "status": item.status,
            "mitigation": item.mitigation,
        }
        for item in contract.confounders
        if item.status != "observed"
    ]
    status = "qualified" if not failures else "quarantined"
    audit = {
        "schema_version": "offline-rl-dataset-audit-v1.0.0",
        "dataset_build_id": str(build.id),
        "dataset_build_digest": build.record_digest,
        "dataset_content_digest": build.content_digest,
        "contract_digest": payload.contract_digest,
        "shadow_journal_digest": contract.shadow_journal_digest,
        "shadow_replay_digest": contract.shadow_replay_digest,
        "transition_count": summary.transition_count,
        "episode_count": summary.episode_count,
        "support_failures": support_failures,
        "causal_availability_valid": temporal_violations == 0,
        "behavior_propensities_complete": summary.missing_propensity_count == 0,
        "reward_reproduced": True,
        "limitations": limitations,
        "status": status,
        "failures": failures,
        "evaluation_authority": False,
        "policy_improvement_authority": False,
        "deployment_authority": False,
        "order_authority": False,
        "capital_authority": False,
    }
    return audit, status


def register_dataset(
    db: Session, payload: OfflineRLDatasetCreate
) -> OfflineRLDatasetContract:
    build = db.get(ResearchDatasetBuild, payload.dataset_build_id)
    if build is None:
        raise OfflineRLConflict("A registered DATA-002 dataset build is required.")
    audit, status = build_audit(payload, build)
    audit_digest = record_digest(audit)
    existing = db.scalar(
        select(OfflineRLDatasetContract).where(
            or_(
                OfflineRLDatasetContract.contract_key == payload.contract_key,
                OfflineRLDatasetContract.audit_digest == audit_digest,
            )
        )
    )
    if existing:
        if existing.audit_digest == audit_digest:
            return existing
        raise OfflineRLConflict("Contract key already exists with different evidence.")
    record = OfflineRLDatasetContract(
        contract_key=payload.contract_key,
        dataset_build_id=payload.dataset_build_id,
        contract=payload.contract.model_dump(mode="json"),
        contract_digest=payload.contract_digest,
        audit=audit,
        audit_digest=audit_digest,
        status=status,
        registered_by=payload.registered_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise OfflineRLConflict("Contract key or audit digest already exists.") from exc
    return record
