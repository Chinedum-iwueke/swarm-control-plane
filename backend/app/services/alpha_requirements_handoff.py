"""Publish and independently review scientific inputs before paid authoring.

Coverage is a predictor-availability claim, not universe membership, event
support, or scientific qualification. The campaign lock owns publication.
"""

import json
import re
from copy import deepcopy
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaignEvent
from app.models.evaluator_routing import EvaluationRoute
from app.models.task import Task
from app.schemas.alpha_discovery import AlphaScientificRequirements
from app.schemas.task import TaskCreate
from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity
from app.services.evaluator_routing import (
    create_route,
    task_producer_identity,
    validated_alpha_strategy_reviews,
)
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


class RequirementsPending(Exception):
    """A durable gate was updated; commit it without creating engineering work."""


def rejection_detail(route, subject_digest, reviews):
    return {
        "route_id": str(route.id), "subject_digest": subject_digest,
        "responsible_component": "scientific_requirements_producer",
        "reconsideration_condition": "Publish an explicit successor specification resolving the recorded blockers, then obtain fresh independent review; do not rewrite rejected evidence.",
        "reviews": [review.model_dump(mode="json") for review in reviews],
        "blockers": sorted({blocker for review in reviews for blocker in review.blockers}),
    }


def bound_review_card(candidate, bindings):
    """Resolve post-admission indexes in a derived view, retaining source identity."""
    symbols = candidate["data"]["instruments"]
    resolved = []
    for symbol in symbols:
        matches = [(index, binding) for index, binding in enumerate(bindings)
            if binding.get("instruments", [binding.get("instrument")]) == [symbol]]
        if len(matches) != 1:
            raise ValueError("Review card requires one exact admitted binding per instrument")
        index, binding = matches[0]
        resolved.append({"instrument": symbol, "binding_index": index, "binding_digest": digest(binding)})
    if len(bindings) != len(symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("Review card admitted basket differs from candidate")
    card = deepcopy(candidate)
    card["source_candidate_document_digest"] = digest(candidate)
    card["source_dataset_binding_index"] = candidate.get("dataset_binding_index")
    card["dataset_binding_scope"] = "review_artifact_bundle.dataset_bindings"
    card["dataset_binding_index"] = resolved[0]["binding_index"] if len(resolved) == 1 else None
    card["admitted_dataset_bindings"] = resolved
    return card


def hydrate_retained_rejection(db, campaign):
    """Restore display details from verified receipts, without reopening work."""
    if campaign.next_action != "scientific_requirements_rejected" or campaign.terminal_reason:
        return
    publication = db.scalar(select(AlphaCampaignEvent).where(
        AlphaCampaignEvent.campaign_id == campaign.id,
        AlphaCampaignEvent.event_type == "scientific_requirements_published",
    ).order_by(AlphaCampaignEvent.created_at.desc(), AlphaCampaignEvent.id.desc()))
    if publication is None:
        return
    route = db.get(EvaluationRoute, publication.payload["route_id"])
    if route is None:
        return
    subject_digest = digest(publication.payload["subject"])
    reviews = validated_alpha_strategy_reviews(db, route, subject_digest=subject_digest,
        producer_agent_id=route.producer.get("agent_id"))
    if reviews and any(review.verdict == "reject" for review in reviews):
        campaign.terminal_reason = {"category": "scientific_requirements_rejected",
            "detail": rejection_detail(route, subject_digest, reviews)}


def _admission_reattestation(db, campaign, producer):
    """Replay immutable admission inputs once; never edit historical lease evidence."""
    if producer.task_type != "alpha_data_admission" or producer.risk_level != 0:
        raise ValueError("Only no-capital native admission can be re-attested")
    number = f"AP-{producer.id}"
    replay = db.scalar(select(Task).where(Task.task_number == number))
    if replay is not None:
        if replay.parent_task_id != producer.id or replay.input_contract != producer.input_contract:
            raise ValueError("Admission re-attestation scope changed")
        return replay
    replay = build_task(TaskCreate(
        task_number=number, project=producer.project, task_type=producer.task_type,
        title="Re-attest native admission provenance",
        objective="Replay the exact admitted scope with lease-time producer identity; preserve prior evidence.",
        parent_task_id=producer.id, created_by="alpha-requirements-director",
        risk_level=0, max_attempts=1,
        input_contract=deepcopy(producer.input_contract),
        required_capabilities=list(producer.required_capabilities),
        allowed_machines=list(producer.allowed_machines),
        expected_outputs=["native admission and predictor coverage with producer custody"],
        acceptance_criteria=["Original immutable inputs", "Same admitted bytes and coverage", "Lease-time identity"],
    ))
    persist_new_task(db, replay)
    from app.services.alpha_campaign import _append_event
    _append_event(db, campaign, "admission_reattestation_requested", "alpha-requirements-director", {
        "original_task_id": str(producer.id), "original_plan_digest": producer.plan_digest,
        "original_result_digest": digest(producer.result), "replay_task_id": str(replay.id),
        "scientific_result": False, "trial_count": 0,
    })
    return replay


def _instant(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("coverage timestamps must be timezone aware")
    return stamp


def build_package(evidence, batch, *, source_commit, allowed_window):
    """Validate native custody and bind compressed clocks to final DATA bindings."""
    candidate = evidence["discovery_candidate"]
    requirements = AlphaScientificRequirements.model_validate(
        candidate["scientific_requirements"]
    ).model_dump(mode="json")
    handoff = evidence["selected_panel_admission"]
    clock = batch["predictor_coverage_evidence"]
    if (
        batch.get("schema_version") != "alpha007-selected-panel-admission-batch-v1.0.0"
        or batch.get("candidate_id") != handoff["candidate_id"]
        or batch.get("candidate_digest") != handoff["candidate_digest"]
        or batch.get("capital_or_order_authority") is not False
        or clock.get("schema_version") != "admitted-research-clock-v1"
        or clock.get("evidence_digest")
        != digest({k: v for k, v in clock.items() if k != "evidence_digest"})
        or clock.get("representation_digest") != digest(evidence["representation_plan"])
        or clock.get("window") != allowed_window
        or clock.get("capital_or_order_authority") is not False
    ):
        raise ValueError("coverage custody or representation binding differs")
    timeframe = re.fullmatch(
        r"([1-9][0-9]*)([mhd])", candidate["data"]["research_timeframe"]
    )
    minutes = (
        int(timeframe[1]) * {"m": 1, "h": 60, "d": 1440}[timeframe[2]]
        if timeframe
        else None
    )
    if (
        minutes != requirements["research_bar_minutes"]
        or minutes != clock["research_bar_minutes"]
    ):
        raise ValueError("scientific requirements and coverage clocks differ")
    if requirements["smoke_bars"] * minutes > 31 * 1440:
        raise ValueError("smoke exceeds 31 days")
    symbols = candidate["data"]["instruments"]
    if len(symbols) != len(set(symbols)) or set(clock["assets"]) != set(symbols):
        raise ValueError("coverage must bind the exact candidate basket")
    receipts = batch["receipts"]
    native = {item["result"]["instrument"]: item for item in receipts}
    if len(native) != len(receipts) or set(native) != set(symbols):
        raise ValueError("native admission basket differs")
    left, right = _instant(allowed_window["start"]), _instant(allowed_window["end"])
    if not timedelta(days=365) <= right - left <= timedelta(days=1095):
        raise ValueError("coverage must remain inside the approved historical envelope")
    step = timedelta(minutes=minutes)
    previous = anchor = None
    count = 0
    for interval in clock["intervals"]:
        start, end = _instant(interval["start"]), _instant(interval["end"])
        anchor = start if anchor is None else anchor
        if (
            not left <= start < end
            or end - step >= right
            or (end - start) % step
            or (start - anchor) % step
            or (previous is not None and start < previous)
        ):
            raise ValueError("invalid or overlapping eligible coverage intervals")
        previous = end
        count += int((end - start) / step)
    if (
        type(clock["eligible_decisions_count"]) is not int
        or count != clock["eligible_decisions_count"]
    ):
        raise ValueError("coverage count does not match retained intervals")
    bound = {}
    for binding in evidence["dataset_bindings"]:
        names = binding.get("instruments", [binding.get("instrument")])
        if len(names) != 1 or names[0] not in native or names[0] in bound:
            raise ValueError("DATA bindings must cover each basket member exactly once")
        symbol = names[0]
        receipt, identity = native[symbol], clock["assets"][symbol]
        result = receipt["result"]
        if (
            receipt.get("source_commit") != source_commit
            or result.get("admitted") is not True
            or not result.get("checks")
            or any(value is not True for value in result["checks"].values())
            or identity["admission_digest"] != digest(receipt)
            or identity["panel_digest"] != result["panel_sha256"]
            or binding["partition_digests"] != [result["panel_sha256"]]
        ):
            raise ValueError("coverage does not match admitted bytes and native source")
        document = {
            "schema_version": "eligible-research-coverage-v1",
            "instrument": symbol,
            "binding_digest": digest(binding),
            "research_bar_minutes": minutes,
            "eligibility_evidence_digest": clock["evidence_digest"],
            "intervals": clock["intervals"],
        }
        bound[symbol] = document | {"receipt_digest": digest(document)}
    if set(bound) != set(symbols):
        raise ValueError("DATA binding basket is incomplete")
    # This digest identifies the proposal. Approval is proved separately by the
    # routed reviewer receipts, never inferred from a hash or model assertion.
    basis = digest(
        {
            "candidate": candidate,
            "clock_digest": clock["evidence_digest"],
            "source_commit": source_commit,
        }
    )
    return {
        "requirements": requirements | {"basis_digest": basis},
        "coverage": [bound[symbol] for symbol in symbols],
        "maximum_history_days": (right - left).days,
        "maximum_bar_variant_work": 20_000_000,
        "eligibility_scope": "fixed_basket_predictor_availability_only",
        "point_in_time_membership_verified": clock.get(
            "point_in_time_membership_verified"
        )
        is True,
        "scientific_certification": False,
    }


def ensure_reviewed_requirements(db, campaign, evidence):
    from app.services.alpha_campaign import (
        _append_event,
        _materialize_strategy_review_tasks,
    )

    def defer(action, detail=None, *, blocked=True):
        campaign.status = "needs_attention" if blocked else "running"
        campaign.phase = "scientific_requirements_review"
        campaign.next_action = action
        campaign.terminal_reason = (
            {"category": action, "detail": detail} if detail else {}
        )
        raise RequirementsPending()

    candidate = evidence.get("discovery_candidate") or {}
    if not candidate.get("scientific_requirements"):
        defer(
            "propose_scientific_requirements",
            "No source-bar count is substituted for scientific support minima.",
        )
    handoff = evidence.get("selected_panel_admission") or {}
    producer = db.get(Task, handoff.get("admission_task_id")) if handoff else None
    if producer is None or producer.status != "succeeded":
        defer("produce_admitted_predictor_coverage")
    from app.models.alpha_discovery import AlphaResearchMandate
    from app.services.alpha_coverage_policy import coverage_window

    mandate = db.get(
        AlphaResearchMandate, campaign.specification.get("research_mandate_id")
    )
    if mandate is None or mandate.mandate_digest != campaign.specification.get(
        "research_mandate_digest"
    ):
        defer("restore_requirements_mandate_binding")
    identity = task_producer_identity(db, producer)
    if identity is None:
        original = producer
        try:
            producer = _admission_reattestation(db, campaign, original)
        except ValueError as exc:
            defer("admission_provenance_reattestation_failed", str(exc))
        if producer.status in {"queued", "leased", "running"}:
            defer("await_admission_provenance_reattestation", blocked=False)
        if producer.status != "succeeded":
            defer("admission_provenance_reattestation_failed", {"replay_task_id": str(producer.id), "status": producer.status})
        identity = task_producer_identity(db, producer)
        old_batch = (original.result or {}).get("summary", {}).get("alpha_data_admission", {})
        new_batch = (producer.result or {}).get("summary", {}).get("alpha_data_admission", {})
        if identity is None:
            defer("admission_provenance_reattestation_failed", "Replay lacks lease-time identity")
        if old_batch.get("predictor_coverage_evidence") != new_batch.get("predictor_coverage_evidence"):
            defer("repair_scientific_requirements_evidence", "Re-attested coverage differs from retained coverage")
    batch = (producer.result or {}).get("summary", {}).get("alpha_data_admission", {})
    try:
        package = build_package(
            evidence,
            batch,
            source_commit=campaign.specification["bulletproof_source_commit"],
            allowed_window=coverage_window(mandate.specification),
        )
    except (KeyError, TypeError, ValueError) as exc:
        defer("repair_scientific_requirements_evidence", str(exc))
    from app.services.alpha_coverage_exposure import successor_context

    try:
        context = successor_context(
            db,
            evidence,
            package,
            mandate,
            campaign.specification["bulletproof_source_commit"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        defer("repair_coverage_exposure_history", str(exc))
    if context is not None:
        evidence["coverage_successor_context"] = context
    from app.services.alpha_requirements_feasibility import planning_task, verified_report, reviewed_successor_inputs

    planning_evidence = {
        "discovery_candidate": candidate,
        "representation_plan": evidence["representation_plan"],
        "dataset_bindings": evidence["dataset_bindings"],
        "window": evidence["window"],
        "validation_requirements": package,
    }
    if context is not None:
        planning_evidence["coverage_successor_context"] = context
    try:
        feasibility_task = planning_task(db, campaign, producer, planning_evidence)
        if feasibility_task.status in {"queued", "leased", "running"}:
            defer("await_native_requirements_feasibility", blocked=False)
        if feasibility_task.status != "succeeded":
            defer("repair_native_requirements_feasibility", {"task_id": str(feasibility_task.id), "status": feasibility_task.status})
        feasibility_identity = task_producer_identity(db, feasibility_task)
        if feasibility_identity is None:
            defer("restore_requirements_producer_identity")
        feasibility = verified_report(feasibility_task, planning_evidence, campaign.specification["bulletproof_source_commit"])
    except (KeyError, TypeError, ValueError) as exc:
        defer("repair_native_requirements_feasibility", str(exc))
    try:
        successor = reviewed_successor_inputs(feasibility, planning_evidence, mandate, campaign.specification["bulletproof_source_commit"]) if feasibility["status"] != "ready" else None
    except (KeyError, TypeError, ValueError) as exc:
        defer("repair_native_requirements_feasibility", str(exc))
    if feasibility["status"] != "ready" and successor is None:
        defer("resolve_native_requirements_feasibility", {
            "task_id": str(feasibility_task.id), "report_digest": feasibility["report_digest"],
            "reasons": feasibility["reasons"], "feature_history": feasibility["feature_history"],
            "validation_plans": feasibility["validation_plans"],
        })
    review_window = evidence["window"]
    if successor is not None:
        package = successor["validation_requirements"]
        review_window = successor["window"]
    package = package | {"native_feasibility_receipt": {
        "task_id": str(feasibility_task.id), "report_digest": feasibility["report_digest"],
        "feature_history": feasibility["feature_history"],
    }}
    prospective = {
        key: value
        for key, value in evidence.items()
        if key not in {"dataset_binding", "instrument", "tier"}
    } | {"validation_requirements": package, "window": review_window}
    if len(prospective) > 20:
        prospective.pop("maximum_variants", None)
    if len(prospective) > 20 or len(json.dumps(prospective, allow_nan=False)) > 46_000:
        # Reserve room for the actual routed receipt within the worker's 48k cap.
        defer("requirements_engineering_context_exceeds_bound")
    if identity is None:
        defer("restore_requirements_producer_identity")
    qualification = {
        "card": bound_review_card(candidate, evidence["dataset_bindings"]),
        "artifact_bundle": {
            "validation_requirements": package,
            "predictor_coverage_evidence": batch["predictor_coverage_evidence"],
            "representation_plan": evidence["representation_plan"],
            "dataset_bindings": evidence["dataset_bindings"],
            "window": review_window,
            "original_window": evidence["window"],
            "coverage_successor_context": context,
            "claim_boundary": "Predictor availability is not universe membership or observed event support.",
            "native_feasibility": feasibility,
            "feasibility_task_id": str(feasibility_task.id),
            "history_interpretation": "Warm-up is prior completed research bars across the composed transformation graph. Reject contradictory prose; event minima are post-execution gates, not inferred observations. Scientific duration is a minimum, with explicit split gaps and target tails in the plan. If a native coverage successor is present, review the changed window, unchanged scientific requirements, historical envelope and exposure exclusions together. The original plan remains deferred; only the successor plans may be ready.",
        },
    }
    if len(json.dumps(qualification).encode()) > 80_000:
        defer("requirements_review_context_exceeds_bound")
    subject = {
        "review_scope": "scientific_requirements",
        "candidate_id": handoff["candidate_id"],
        "source_commit": campaign.specification["bulletproof_source_commit"],
        "card_digest": digest(candidate),
        "artifact_bundle_digest": digest(qualification["artifact_bundle"]),
        "producer_agent_ids": sorted({str(identity["agent_id"]), str(feasibility_identity["agent_id"])}),
        "producer_task_id": str(producer.id),
    }
    publications = db.scalars(
        select(AlphaCampaignEvent).where(
            AlphaCampaignEvent.campaign_id == campaign.id,
            AlphaCampaignEvent.event_type == "scientific_requirements_published",
        )
    ).all()
    published = next(
        (event for event in publications if event.payload["subject"] == subject), None
    )
    if published is None:
        route = create_route(
            db,
            EvaluationRouteCreate(
                subject_type="alpha_strategy_qualification",
                subject_id=f"requirements:{handoff['candidate_id']}",
                subject_digest=digest(subject),
                producer=ProducerIdentity.model_validate(
                    identity | {"actor": str(identity["agent_id"])}
                ),
                required_review_kinds=["strategy_spec", "causality_leakage"],
                requested_by="alpha-requirements-director",
            ),
        )
        published = _append_event(
            db,
            campaign,
            "scientific_requirements_published",
            "alpha-requirements-director",
            {
                "subject": subject,
                "qualification": qualification,
                "route_id": str(route.id),
            },
        )
    else:
        if published.payload["qualification"] != qualification:
            raise HTTPException(409, "Scientific requirements publication changed.")
        route = db.get(EvaluationRoute, published.payload["route_id"])
        if route is None:
            raise HTTPException(409, "Scientific requirements route is missing.")
    _materialize_strategy_review_tasks(db, route, subject, qualification)
    if route.status == "blocked":
        defer("repair_requirements_review_routing")
    reviews = validated_alpha_strategy_reviews(
        db,
        route,
        subject_digest=digest(subject),
        producer_agent_id=identity["agent_id"],
    )
    if reviews is None:
        defer("await_independent_scientific_requirements_review", blocked=False)
    if any(review.verdict != "approve" for review in reviews):
        defer("scientific_requirements_rejected", rejection_detail(route, digest(subject), reviews))
    if successor is not None:
        # Only the new engineering evidence changes, after both reviews. The
        # original candidate, admission, task and publication remain immutable.
        evidence["window"] = deepcopy(review_window)
        evidence.pop("coverage_successor_context", None)
        package = package | {"coverage_successor_receipt": {
            "publication_digest": published.event_digest,
            "route_id": str(route.id),
            "successor_digest": feasibility["coverage_successor_proposal"]["successor_digest"],
            "parent_task_id": str(feasibility_task.id),
        }}
    return package | {
        "review_receipt": {
            "route_id": str(route.id),
            "publication_digest": published.event_digest,
            "subject_digest": digest(subject),
        }
    }
