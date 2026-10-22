from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Artifact, Task, TaskEvent
from app.models.alpha_campaign import AlphaCampaign


def serialize_backtest(
    task: Task,
    campaign: AlphaCampaign | None = None,
    progress: dict | None = None,
    artifacts: list[Artifact] | None = None,
) -> dict:
    contract = task.input_contract or {}
    result = task.result or {}
    summary = result.get("summary", {})
    attempt = summary.get("alpha_campaign_attempt") or {}
    handoff = result.get("downstream_handoff") or {}
    publication = handoff.get("publication_envelope") or {}
    trial = publication.get("trial") or {}
    producer_gates = (
        publication.get("producer_gate_report")
        or handoff.get("producer_gate_report")
        or {}
    )
    gates = attempt.get("gate_report") or producer_gates
    stage = contract.get("stage", "execute")
    terminal = task.status in {"succeeded", "failed", "cancelled"}
    has_native_receipt = (
        terminal
        and stage == "execute"
        and _has_native_receipt(summary, attempt, publication, trial)
    )
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
        "trial_count": attempt.get("trial_count")
        if attempt
        else (1 if trial else None),
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
        "gate_states": _gate_states(gates),
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
        if has_native_receipt
        else "no_native_terminal_receipt",
        "scientific_contract": _scientific_contract(
            contract, result, summary, publication, trial, attempt, progress or {}
        ),
        "terminal_receipt": {
            "present": has_native_receipt,
            "digest": summary.get("receipt_digest") if has_native_receipt else None,
            "schema_version": publication.get("schema_version")
            if has_native_receipt
            else None,
            "bundle_digest": trial.get("bundle_digest") if has_native_receipt else None,
        },
        "artifacts": [_artifact_reference(item) for item in (artifacts or [])],
    }


_REQUIRED_GATES = (
    "truth_certified",
    "point_in_time_valid",
    "reproducible",
    "out_of_sample_evaluated",
    "cost_stress_evaluated",
    "selection_bias_audited",
    "independent_review_complete",
    "required_trade_logging_complete",
    "shadow_eligible",
)


def _has_native_receipt(
    summary: dict, attempt: dict, publication: dict, trial: dict
) -> bool:
    receipt_digest = summary.get("receipt_digest")
    complete_attempt = (
        attempt.get("produced_by") == "bulletproof_bt"
        and bool(attempt.get("attempt_key"))
        and bool(attempt.get("source_commit"))
        and bool(attempt.get("evidence_digests"))
        and isinstance(attempt.get("gate_report"), dict)
    )
    complete_publication = all(
        (
            publication.get("schema_version"),
            trial.get("trial_id"),
            trial.get("code_digest"),
            trial.get("bundle_digest"),
            trial.get("representation_contract_digest"),
            trial.get("search_plan_digest"),
        )
    )
    return bool(receipt_digest and (complete_attempt or complete_publication))


def _gate_states(gates: dict) -> dict[str, str]:
    return {
        key: (
            "passed"
            if gates.get(key) is True
            else "failed"
            if gates.get(key) is False
            else "not_run"
        )
        for key in _REQUIRED_GATES
    }


def _scientific_contract(
    contract: dict,
    result: dict,
    summary: dict,
    publication: dict,
    trial: dict,
    attempt: dict,
    progress: dict,
) -> dict:
    hypothesis = (
        summary.get("hypothesis_card")
        or publication.get("hypothesis_card")
        or contract.get("hypothesis_card")
        or {}
    )
    experiment = publication.get("experiment") or {}
    durable = publication.get("durable_evidence") or {}
    representation = contract.get("representation_plan") or {}
    qualification = contract.get("qualification") or {}
    metrics = trial.get("metrics") or summary.get("metrics") or {}
    bindings = contract.get("dataset_bindings") or []
    instruments = contract.get("instruments") or [contract.get("instrument")]
    instruments = [value for value in instruments if value]
    return {
        "hypothesis": {
            "id": attempt.get("hypothesis_id")
            or (contract.get("reusable_strategy") or {}).get("hypothesis_id"),
            "digest": attempt.get("hypothesis_digest") or hypothesis.get("card_digest"),
            "question_digest": contract.get("question_digest"),
            "card": hypothesis,
        },
        "dataset": {
            "build_id": contract.get("dataset_build_id"),
            "key": contract.get("dataset_key"),
            "digest": contract.get("dataset_digest"),
            "venue": contract.get("venue"),
            "instruments": instruments,
            "bindings": [
                {
                    key: item.get(key)
                    for key in (
                        "dataset_build_id",
                        "dataset_key",
                        "dataset_digest",
                        "instrument",
                        "venue",
                        "partition_digest",
                    )
                }
                for item in bindings
                if isinstance(item, dict)
            ],
        },
        "representation": {
            "source_timeframe": contract.get("timeframe"),
            "research_timeframe": contract.get("research_timeframe"),
            "resampling_policy": contract.get("resampling_policy"),
            "plan": representation,
            "contract_digest": trial.get("representation_contract_digest")
            or durable.get("representation_contract_digest"),
            "window_start": contract.get("window_start"),
            "window_end": contract.get("window_end"),
        },
        "strategy": {
            "source_commit": result.get("base_commit") or contract.get("base_ref"),
            "code_digest": trial.get("code_digest"),
            "binding": contract.get("reusable_strategy"),
        },
        "search": {
            "maximum_variants": contract.get("max_variants"),
            "declared_variants": metrics.get("declared_variant_count"),
            "selected_variant_index": metrics.get("selected_variant_index"),
            "selection_basis": metrics.get("selection_basis"),
            "search_plan_digest": trial.get("search_plan_digest"),
        },
        "execution": {
            "trial_id": trial.get("trial_id"),
            "trial_count": attempt.get("trial_count") or (1 if trial else None),
            "started_at": trial.get("started_at"),
            "ended_at": trial.get("ended_at"),
            "worker_allocation": progress.get("worker_allocation")
            or progress.get("active_workers"),
            "capacity_governed": progress.get("capacity_governed"),
        },
        "evaluation": {
            "metrics": metrics,
            "splits": experiment.get("splits") or qualification.get("splits"),
            "costs": experiment.get("costs") or qualification.get("costs"),
            "leakage_review": qualification.get("leakage_review")
            or (
                "passed"
                if (attempt.get("gate_report") or {}).get("point_in_time_valid") is True
                else "failed"
                if (attempt.get("gate_report") or {}).get("point_in_time_valid")
                is False
                else "not_run"
            ),
            "selection_bias_audit_digest": durable.get("selection_bias_audit_digest"),
            "required_trade_logging_digest": durable.get(
                "required_trade_logging_digest"
            ),
            "hypothesis_evaluation": trial.get("hypothesis_evaluation"),
        },
    }


def _artifact_reference(item: Artifact) -> dict:
    return {
        key: getattr(item, key, None)
        for key in (
            "id",
            "task_id",
            "name",
            "artifact_type",
            "size_bytes",
            "sha256",
            "location",
            "workflow",
            "workflow_version",
            "source_commit",
            "verification_status",
            "created_at",
        )
    }


def overview(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    category: str = "all",
    tier: str = "all",
) -> dict:
    # This is a custody projection, never a quantitative evaluator or scheduler.
    # Draft, qualification and engineering tasks share the alpha task type but are
    # not backtests. Only the governed execution stage may enter this projection.
    predicate = Task.task_type.in_(["alpha_research_execution", "research_experiment"])
    predicate &= Task.input_contract["stage"].astext == "execute"
    task_status_counts = dict(
        db.execute(
            select(Task.status, func.count()).where(predicate).group_by(Task.status)
        ).all()
    )
    terminal_predicate = Task.status.in_(["succeeded", "failed", "cancelled"])
    receipt_digest_present = Task.result["summary"]["receipt_digest"].astext.is_not(
        None
    )
    receipt_shape_present = or_(
        and_(
            Task.result["summary"]["alpha_campaign_attempt"]["produced_by"].astext
            == "bulletproof_bt",
            Task.result["summary"]["alpha_campaign_attempt"][
                "attempt_key"
            ].astext.is_not(None),
            Task.result["summary"]["alpha_campaign_attempt"][
                "source_commit"
            ].astext.is_not(None),
            Task.result["summary"]["alpha_campaign_attempt"]["evidence_digests"].is_not(
                None
            ),
            Task.result["summary"]["alpha_campaign_attempt"]["gate_report"].is_not(
                None
            ),
        ),
        and_(
            Task.result["downstream_handoff"]["publication_envelope"][
                "schema_version"
            ].astext.is_not(None),
            Task.result["downstream_handoff"]["publication_envelope"]["trial"][
                "bundle_digest"
            ].astext.is_not(None),
            Task.result["downstream_handoff"]["publication_envelope"]["trial"][
                "trial_id"
            ].astext.is_not(None),
            Task.result["downstream_handoff"]["publication_envelope"]["trial"][
                "code_digest"
            ].astext.is_not(None),
            Task.result["downstream_handoff"]["publication_envelope"]["trial"][
                "representation_contract_digest"
            ].astext.is_not(None),
            Task.result["downstream_handoff"]["publication_envelope"]["trial"][
                "search_plan_digest"
            ].astext.is_not(None),
        ),
    )
    completed_backtests_all = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                predicate,
                terminal_predicate,
                receipt_digest_present,
                receipt_shape_present,
            )
        )
        or 0
    )
    terminal_tasks = sum(
        task_status_counts.get(state, 0)
        for state in ("succeeded", "failed", "cancelled")
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
    completed_backtests = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                predicate,
                terminal_predicate,
                receipt_digest_present,
                receipt_shape_present,
            )
        )
        or 0
    )
    counts = {
        **task_status_counts,
        "completed_backtests": completed_backtests,
        "completed_backtests_all": completed_backtests_all,
        "terminal_tasks_without_receipt_all": max(
            0, terminal_tasks - completed_backtests_all
        ),
    }
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
    artifacts = db.scalars(
        select(Artifact)
        .where(Artifact.task_id.in_([task.id for task in tasks]))
        .order_by(Artifact.task_id, Artifact.created_at, Artifact.id)
    ).all()
    artifacts_by_task: dict[str, list[Artifact]] = {}
    for artifact in artifacts:
        artifacts_by_task.setdefault(str(artifact.task_id), []).append(artifact)
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
                artifacts_by_task.get(str(task.id), []),
            )
            for task in tasks
        ],
        "claim_boundary": "Task success is not backtest success. Native receipts establish research outcomes; shadow eligibility is not admission or live authority.",
    }
