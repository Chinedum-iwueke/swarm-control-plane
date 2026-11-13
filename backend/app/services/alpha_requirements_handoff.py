"""Publish and independently review scientific inputs before paid authoring.

Coverage is a predictor-availability claim, not universe membership, event
support, or scientific qualification. The campaign lock owns publication.
"""

import json
import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaignEvent
from app.models.evaluator_routing import EvaluationRoute
from app.models.task import Task
from app.schemas.alpha_discovery import AlphaScientificRequirements
from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity
from app.services.evaluator_routing import (
    create_route,
    task_producer_identity,
    validated_alpha_strategy_reviews,
)
from app.services.graph import digest_document as digest


class RequirementsPending(Exception):
    """A durable gate was updated; commit it without creating engineering work."""


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
    prospective = {
        key: value
        for key, value in evidence.items()
        if key not in {"dataset_binding", "instrument", "tier"}
    } | {"validation_requirements": package}
    if len(prospective) > 20 or len(json.dumps(prospective, allow_nan=False)) > 46_000:
        # Reserve room for the actual routed receipt within the worker's 48k cap.
        defer("requirements_engineering_context_exceeds_bound")
    identity = task_producer_identity(db, producer)
    if identity is None:
        defer("restore_requirements_producer_identity")
    qualification = {
        "card": candidate,
        "artifact_bundle": {
            "validation_requirements": package,
            "predictor_coverage_evidence": batch["predictor_coverage_evidence"],
            "representation_plan": evidence["representation_plan"],
            "dataset_bindings": evidence["dataset_bindings"],
            "window": evidence["window"],
            "claim_boundary": "Predictor availability is not universe membership or observed event support.",
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
        "producer_agent_ids": [str(identity["agent_id"])],
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
        defer("scientific_requirements_rejected")
    return package | {
        "review_receipt": {
            "route_id": str(route.id),
            "publication_digest": published.event_digest,
            "subject_digest": digest(subject),
        }
    }
