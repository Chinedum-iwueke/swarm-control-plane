from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskEvent
from app.models.alpha_campaign import AlphaCampaign


def serialize_backtest(
    task: Task, campaign: AlphaCampaign | None = None, progress: dict | None = None
) -> dict:
    contract = task.input_contract or {}
    result = task.result or {}
    summary = result.get("summary", {})
    attempt = summary.get("alpha_campaign_attempt") or {}
    handoff = result.get("downstream_handoff") or {}
    publication = handoff.get("publication_envelope") or {}
    trial = publication.get("trial") or {}
    producer_gates = handoff.get("producer_gate_report") or {}
    gates = attempt.get("gate_report") or producer_gates
    has_native_receipt = bool(
        attempt
        or (
            publication.get("schema_version")
            and trial.get("bundle_digest")
            and summary.get("receipt_digest")
        )
    )
    stage = contract.get("stage", "execute")
    terminal = task.status in {"succeeded", "failed", "cancelled"}
    category = (
        "finished"
        if terminal
        else "running"
        if task.status in {"running", "leased"}
        else "waiting"
    )
    return {
        "task_id": str(task.id),
        "task_number": task.task_number,
        "question": contract.get("question") or task.title,
        "status": task.status,
        "category": category,
        "stage": stage,
        "tier": contract.get("tier"),
        "instrument": contract.get("instrument"),
        "dataset_key": contract.get("dataset_key"),
        "dataset_digest": contract.get("dataset_digest"),
        "window_start": contract.get("window_start"),
        "window_end": contract.get("window_end"),
        "max_variants": contract.get("max_variants"),
        "base_ref": contract.get("base_ref"),
        "heartbeat_at": task.last_execution_heartbeat_at,
        "progress": {
            key: (progress or {})[key]
            for key in ("phase", "elapsed_seconds", "capacity_governed")
            if key in (progress or {})
        },
        "created_at": task.created_at,
        "completed_at": task.completed_at,
        "campaign_id": contract.get("campaign_id"),
        "campaign_phase": campaign.phase if campaign else None,
        "outcome": attempt.get("outcome") or trial.get("result_disposition"),
        "trial_count": attempt.get("trial_count") if attempt else (1 if trial else None),
        "failure_stage": attempt.get("failure_stage"),
        "disposition": summary.get("disposition"),
        "failed_gates": gates.get("failed_gates", []),
        "gate_report": {
            key: gates[key]
            for key in (
                "reproducible",
                "point_in_time_valid",
                "cost_stress_evaluated",
                "selection_bias_audited",
                "out_of_sample_evaluated",
                "independent_review_complete",
                "truth_certified",
                "shadow_eligible",
            )
            if key in gates
        },
        "receipt_digest": summary.get("receipt_digest"),
        "metrics": {
            key: value
            for key, value in (summary.get("metrics") or {}).items()
            if key
            in (
                "oos_trades",
                "oos_mean_net_r",
                "double_cost_oos_mean_net_r",
                "declared_variant_count",
                "selected_variant_index",
                "selection_basis",
            )
        },
        "evidence_digests": attempt.get("evidence_digests", [])
        or [
            value
            for value in (
                trial.get("bundle_digest"),
                trial.get("bundle_manifest_digest"),
                trial.get("representation_contract_digest"),
                trial.get("market_model_bundle_digest"),
                trial.get("search_plan_digest"),
            )
            if value
        ],
        "error_category": (task.failure or {}).get("error_category"),
        "execution_class": summary.get("execution_class")
        or publication.get("execution_class")
        or contract.get("execution_class", "qualification"),
        "qualification_authority": summary.get("qualification_authority")
        if "qualification_authority" in summary
        else publication.get("qualification_authority"),
        "promotion": "shadow_review_requested"
        if campaign and campaign.status == "shadow_candidate"
        else "not_established",
        "execution_evidence": "native_terminal_receipt"
        if has_native_receipt and stage == "execute"
        else "no_native_terminal_receipt",
    }


def overview(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    category: str = "all",
    tier: str = "all",
) -> dict:
    # This is a custody projection, never a quantitative evaluator or scheduler.
    predicate = Task.task_type.in_(["alpha_research_execution", "research_experiment"])
    counts = dict(
        db.execute(
            select(Task.status, func.count()).where(predicate).group_by(Task.status)
        ).all()
    )
    if category == "finished":
        predicate &= Task.status.in_(["succeeded", "failed", "cancelled"])
    elif category == "running":
        predicate &= Task.status.in_(["running", "leased"])
    elif category == "waiting":
        predicate &= Task.status.not_in(
            ["succeeded", "failed", "cancelled", "running", "leased"]
        )
    if tier != "all":
        predicate &= Task.input_contract["tier"].astext == tier
    total = db.scalar(select(func.count()).select_from(Task).where(predicate)) or 0
    tasks = db.scalars(
        select(Task)
        .where(predicate)
        .order_by(Task.created_at.desc(), Task.id)
        .offset(offset)
        .limit(limit)
    ).all()
    from uuid import UUID

    campaign_ids = set()
    for task in tasks:
        try:
            campaign_ids.add(UUID(str((task.input_contract or {}).get("campaign_id"))))
        except ValueError:
            pass
    campaigns = {
        str(item.id): item
        for item in db.scalars(
            select(AlphaCampaign).where(AlphaCampaign.id.in_(campaign_ids))
        ).all()
    }
    events = db.scalars(
        select(TaskEvent)
        .where(
            TaskEvent.task_id.in_([task.id for task in tasks]),
            TaskEvent.event_type == "task_heartbeat",
        )
        .distinct(TaskEvent.task_id)
        .order_by(TaskEvent.task_id, TaskEvent.id.desc())
    ).all()
    progress = {
        str(event.task_id): (event.payload or {}).get("progress", {})
        for event in events
    }
    return {
        "generated_at": datetime.now(UTC),
        "counts": counts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(tasks) < total,
        "items": [
            serialize_backtest(
                task,
                campaigns.get(str((task.input_contract or {}).get("campaign_id"))),
                progress.get(str(task.id)),
            )
            for task in tasks
        ],
        "claim_boundary": "Task success is not backtest success. Native receipts establish research outcomes; shadow eligibility is not admission or live authority.",
    }
