"""Conservative, bounded exposure snapshots for governed research lineages."""

from datetime import datetime

from sqlalchemy import or_, select

from app.models.alpha_campaign import AlphaCampaignAttempt, AlphaCampaignEvent
from app.models.task import Task
from app.services.graph import digest_document as digest


def exposure_ledger(tasks, attempts, *, lineage_digest):
    """Unknown execution or missing windows cannot be represented as no exposure.

    This is the control-plane research ledger, not a claim that nobody outside
    this governed system has ever examined the market data.
    """
    intervals, records, retained_attempts = [], [], set()
    for task in tasks:
        contract = task.input_contract
        if contract.get("stage") in {"draft", "qualify"}:
            continue
        if task.status in {
            "queued",
            "pending_approval",
            "leased",
            "running",
            "in_progress",
        }:
            raise ValueError("matching research execution is pending or in flight")
        if not task.attempt_count and task.status != "succeeded":
            continue
        window = {
            "start": contract.get("window_start"),
            "end": contract.get("window_end"),
        }
        try:
            start, end = (
                datetime.fromisoformat(window[key].replace("Z", "+00:00"))
                for key in ("start", "end")
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "prior research exposure has no reconstructible interval"
            ) from exc
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("prior research exposure interval is invalid")
        intervals.append(window)
        records.append(
            {
                "task_id": str(task.id),
                "plan_digest": task.plan_digest,
                "contract_digest": digest(contract),
                "status": task.status,
                "attempt_count": task.attempt_count,
            }
        )
        attempt = (
            (task.result or {}).get("summary", {}).get("alpha_campaign_attempt", {})
        )
        if attempt.get("attempt_key"):
            retained_attempts.add(
                (str(contract.get("campaign_id")), attempt["attempt_key"])
            )
    # An attempt without any retained execution contract is evidence of a gap,
    # even when its terminal outcome was negative. Never fill that gap with [].
    if any(
        a.trial_count and (str(a.campaign_id), a.attempt_key) not in retained_attempts
        for a in attempts
    ):
        raise ValueError(
            "scientific attempts exist without retained exposure contracts"
        )
    ledger = {
        "schema_version": "governed-research-exposure-ledger-v1",
        "scope": "same_question_or_source_candidate_governed_task_history",
        "lineage_digest": lineage_digest,
        "complete": True,
        "intervals": sorted(intervals, key=lambda item: (item["start"], item["end"])),
        "source_records": sorted(records, key=lambda item: item["task_id"]),
        "attempt_records": sorted(
            [{"id": str(a.id), "trial_count": a.trial_count} for a in attempts],
            key=lambda item: item["id"],
        ),
    }
    return ledger | {"ledger_digest": digest(ledger)}


def successor_context(db, evidence, package, mandate, source_commit):
    policy = (mandate.specification.get("historical_window_policy") or {}).get(
        "coverage_replanning"
    )
    if policy is None:
        return None
    immutable = {
        "requirements": package["requirements"],
        "dataset_bindings": evidence["dataset_bindings"],
        "instruments": evidence["discovery_candidate"]["data"]["instruments"],
        "source_commit": source_commit,
        "variants": evidence["discovery_candidate"]["parameter_budget"][
            "maximum_variants"
        ],
        "maximum_history_days": package["maximum_history_days"],
        "maximum_bar_variant_work": package["maximum_bar_variant_work"],
        "approved_window": evidence["window"],
    }
    # Limit before materializing JSON. An oversized history needs a dedicated
    # audit job, not a truncated "complete" ledger inside the API transaction.
    tasks = db.scalars(
        select(Task)
        .where(
            Task.task_type == "alpha_research_execution",
            or_(
                Task.input_contract["question_digest"].astext
                == evidence["question_digest"],
                Task.input_contract["source_candidate_digest"].astext
                == evidence["source_candidate_digest"],
            ),
        )
        .order_by(Task.id)
        .limit(1001)
    ).all()
    attempts = db.scalars(
        select(AlphaCampaignAttempt)
        .where(
            or_(
                AlphaCampaignAttempt.question_digest == evidence["question_digest"],
                AlphaCampaignAttempt.source_candidate_digest
                == evidence["source_candidate_digest"],
            ),
        )
        .order_by(AlphaCampaignAttempt.id)
        .limit(1001)
    ).all()
    if len(tasks) > 1000 or len(attempts) > 1000:
        raise ValueError("exposure history exceeds synchronous audit bound")
    lineage = digest(immutable)
    ledger = exposure_ledger(tasks, attempts, lineage_digest=lineage)
    publications = db.scalars(
        select(AlphaCampaignEvent)
        .where(
            AlphaCampaignEvent.event_type == "coverage_successor_published",
            AlphaCampaignEvent.payload["proposal"]["lineage_digest"].astext == lineage,
        )
        .order_by(AlphaCampaignEvent.id)
        .limit(4)
    ).all()
    if len(publications) > policy["maximum_successors"]:
        raise ValueError("coverage successor lineage exceeds approved budget")
    return {
        "mandate_digest": mandate.mandate_digest,
        "policy": policy,
        "prior_successors": [event.payload["proposal"] for event in publications],
        "exposure_ledger": ledger,
    }
