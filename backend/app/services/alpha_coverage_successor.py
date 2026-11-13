"""Durable, independently reviewed coverage recovery under the campaign lock.

Proposals originate in the deterministic native preflight, not in model prose.
The existing campaign event chain is the publication ledger; task numbers are
unique, making repeated reconciliation and process restarts idempotent.
"""

import json
from copy import deepcopy
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaignEvent
from app.models.alpha_discovery import AlphaResearchMandate
from app.models.evaluator_routing import EvaluationRoute
from app.models.task import Task
from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity
from app.schemas.task import TaskCreate
from app.services.alpha_coverage_exposure import successor_context
from app.services.evaluator_routing import (
    create_route,
    task_producer_identity,
    validated_alpha_strategy_reviews,
)
from app.services.graph import digest_document
from app.services.tasks import build_task, persist_new_task


def validate_proposal(parent, mandate, proposal):
    evidence = json.loads(parent.input_contract["evidence_context"])
    execution = parent.result or (parent.failure or {}).get("execution_evidence", {})
    parent_plan = execution["summary"]["validation_plans"]["scientific"]
    return validate_native_proposal(evidence, parent_plan, parent.input_contract["base_ref"], mandate, proposal)


def validate_native_proposal(evidence, parent_plan, source_commit, mandate, proposal):
    """Validate the same recovery contract before or after strategy engineering."""
    package = evidence["validation_requirements"]
    context = evidence["coverage_successor_context"]
    policy = mandate.specification["historical_window_policy"]["coverage_replanning"]
    if parent_plan["plan_digest"] != digest_document(
        {k: v for k, v in parent_plan.items() if k != "plan_digest"}
    ) or parent_plan.get("reasons") != [
        "insufficient_contiguous_eligible_basket_history"
    ]:
        raise ValueError("successor requires retained coverage-only preflight failure")
    if (
        context["mandate_digest"] != mandate.mandate_digest
        or context["policy"] != policy
        or proposal.get("mandate_digest") != mandate.mandate_digest
        or proposal.get("policy_digest") != digest_document(policy)
        or proposal.get("successor_digest")
        != digest_document(
            {k: v for k, v in proposal.items() if k != "successor_digest"}
        )
        or proposal.get("status") != "proposed"
        or proposal.get("reasons") != []
        or proposal.get("execution_authority") is not False
        or proposal.get("requires_independent_review") is not True
        or proposal.get("scientific_certification") is not False
    ):
        raise ValueError("coverage proposal differs from its approved scope")
    prior = context["prior_successors"]
    expected_parent = (
        prior[-1]["successor_digest"] if prior else parent_plan["plan_digest"]
    )
    if proposal.get("parent_digest") != expected_parent:
        raise ValueError("successor parent digest differs from retained preflight")
    if (
        proposal.get("ordinal") != len(prior) + 1
        or len(prior) >= policy["maximum_successors"]
    ):
        raise ValueError("coverage successor budget or lineage mismatch")
    inputs = proposal["planning_inputs"]
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
    }
    if any(inputs.get(key) != value for key, value in immutable.items()):
        raise ValueError("coverage successor changed the scientific contract")
    if inputs["approved_window"] != {
        "start": policy["envelope_start"],
        "end": policy["envelope_end"],
    }:
        raise ValueError("coverage successor expanded historical authority")
    lineage = digest_document(immutable | {"approved_window": evidence["window"]})
    ledger = context["exposure_ledger"]
    if (
        proposal.get("lineage_digest") != lineage
        or ledger.get("lineage_digest") != lineage
        or ledger.get("complete") is not True
        or proposal.get("exposure_ledger_digest") != ledger.get("ledger_digest")
        or ledger.get("ledger_digest")
        != digest_document({k: v for k, v in ledger.items() if k != "ledger_digest"})
        or proposal.get("coverage_digest") != digest_document(package["coverage"])
    ):
        raise ValueError("coverage successor exposure or evidence lineage mismatch")
    plan = proposal["scientific_plan"]
    if plan.get("plan_digest") != digest_document(
        {k: v for k, v in plan.items() if k != "plan_digest"}
    ):
        raise ValueError("coverage successor plan digest mismatch")
    if plan.get("status") != "ready" or plan.get("execution_authority") is not False:
        raise ValueError("coverage successor is not a ready no-authority plan")
    return evidence


def reconcile_coverage_successor(db, campaign, parent):
    """Return (successor, handled); caller already holds the campaign row lock."""
    from app.services.alpha_campaign import (
        _append_event,
        _materialize_strategy_review_tasks,
    )

    if parent.status != "failed":
        return None, False
    result = parent.result or (parent.failure or {}).get("execution_evidence", {})
    proposal = (result.get("summary") or {}).get("coverage_successor_proposal")
    if not isinstance(proposal, dict):
        return None, False
    number = f"{parent.task_number}-COV1"
    existing = db.scalar(select(Task).where(Task.task_number == number))
    if existing is not None:
        if existing.parent_task_id != parent.id:
            raise HTTPException(409, "Coverage successor task identity conflict.")
        return existing, True
    mandate = db.scalar(
        select(AlphaResearchMandate).where(
            AlphaResearchMandate.id == campaign.specification.get("research_mandate_id")
        )
    )
    if (
        mandate is None
        or mandate.status != "active"
        or mandate.mandate_digest
        != campaign.specification.get("research_mandate_digest")
        or not mandate.valid_from <= datetime.now(UTC) < mandate.valid_until
    ):
        campaign.status = "needs_attention"
        campaign.next_action = "renew_weekly_research_mandate"
        return None, True
    if (
        parent.approval_policy.get("kind") != "bounded_hypothesis_engineering"
        or parent.approval_policy.get("founder_approval_exempt") is not True
    ):
        raise HTTPException(
            409, "Coverage recovery cannot broaden engineering authority."
        )
    try:
        evidence = validate_proposal(parent, mandate, proposal)
        current_context = successor_context(
            db,
            evidence,
            evidence["validation_requirements"],
            mandate,
            parent.input_contract["base_ref"],
        )
        if (
            current_context is None
            or current_context["exposure_ledger"]
            != evidence["coverage_successor_context"]["exposure_ledger"]
        ):
            raise ValueError("coverage exposure history changed after frozen preflight")
    except (KeyError, TypeError, ValueError) as exc:
        campaign.status = "needs_attention"
        campaign.next_action = "repair_coverage_successor_evidence"
        campaign.terminal_reason = {
            "category": "coverage_successor_invalid",
            "detail": str(exc),
        }
        return None, True
    identity = task_producer_identity(db, parent)
    if identity is None:
        campaign.status = "needs_attention"
        campaign.next_action = "restore_coverage_producer_identity"
        return None, True
    qualification = {
        "card": evidence["discovery_candidate"],
        "artifact_bundle": {
            "proposal": proposal,
            "parent_validation_requirements": evidence["validation_requirements"],
            "parent_window": evidence["window"],
            "coverage_successor_context": evidence["coverage_successor_context"],
        },
    }
    if len(json.dumps(qualification, allow_nan=False).encode()) > 80_000:
        campaign.status = "needs_attention"
        campaign.next_action = "coverage_review_context_exceeds_bound"
        return None, True
    subject = {
        "review_scope": "coverage_window_successor",
        "parent_task_id": str(parent.id),
        "parent_plan_digest": parent.plan_digest,
        "source_commit": parent.input_contract["base_ref"],
        "card_digest": digest_document(qualification["card"]),
        "artifact_bundle_digest": digest_document(qualification["artifact_bundle"]),
        "producer_agent_ids": [str(identity["agent_id"])],
    }
    events = db.scalars(
        select(AlphaCampaignEvent).where(
            AlphaCampaignEvent.campaign_id == campaign.id,
            AlphaCampaignEvent.event_type == "coverage_successor_published",
        )
    ).all()
    published = next(
        (e for e in events if e.payload.get("parent_task_id") == str(parent.id)), None
    )
    if published is None:
        producer = ProducerIdentity.model_validate(
            identity | {"actor": str(identity["agent_id"])}
        )
        route = create_route(
            db,
            EvaluationRouteCreate(
                subject_type="alpha_strategy_qualification",
                subject_id=f"coverage:{parent.id}",
                subject_digest=digest_document(subject),
                producer=producer,
                required_review_kinds=["strategy_spec", "causality_leakage"],
                requested_by="alpha-coverage-director",
            ),
        )
        published = _append_event(
            db,
            campaign,
            "coverage_successor_published",
            "alpha-coverage-director",
            {
                "parent_task_id": str(parent.id),
                "proposal": proposal,
                "route_id": str(route.id),
                "subject": subject,
            },
        )
    else:
        if (
            published.payload["proposal"] != proposal
            or published.payload["subject"] != subject
        ):
            raise HTTPException(409, "Published coverage successor is immutable.")
        route = db.get(EvaluationRoute, published.payload["route_id"])
        if route is None:
            raise HTTPException(409, "Published coverage review route is missing.")
    _materialize_strategy_review_tasks(db, route, subject, qualification)
    if route.status == "blocked":
        campaign.phase = "coverage_successor_review"
        campaign.status = "needs_attention"
        campaign.next_action = "repair_coverage_review_routing"
        return None, True
    reviews = validated_alpha_strategy_reviews(
        db,
        route,
        subject_digest=digest_document(subject),
        producer_agent_id=identity["agent_id"],
    )
    campaign.phase = "coverage_successor_review"
    if reviews is None:
        campaign.status = "running"
        campaign.next_action = "await_independent_coverage_successor_review"
        return None, True
    if any(review.verdict != "approve" for review in reviews):
        campaign.status = "needs_attention"
        campaign.next_action = "coverage_successor_rejected"
        return None, True
    contract = deepcopy(parent.input_contract)
    successor_evidence = deepcopy(evidence)
    parts = proposal["scientific_plan"]["partitions"]
    successor_evidence["window"] = {
        "start": parts["feature_warmup"]["start"],
        "end": parts["target_tail"]["end"],
    }
    successor_evidence["validation_requirements"]["coverage"] = proposal[
        "planning_inputs"
    ]["coverage"]
    # A changed contract gets its own review and preflight. No implicit recursive
    # authoring retries; later recovery needs a newly bound exposure/lineage ledger.
    successor_evidence.pop("coverage_successor_context", None)
    successor_evidence["coverage_successor_receipt"] = {
        "event_digest": published.event_digest,
        "route_id": str(route.id),
        "successor_digest": proposal["successor_digest"],
        "parent_task_id": str(parent.id),
    }
    contract["evidence_context"] = json.dumps(
        successor_evidence, sort_keys=True, allow_nan=False
    )
    task = build_task(
        TaskCreate(
            task_number=number,
            project=parent.project,
            task_type="engineering_mission",
            title=parent.title,
            objective=parent.objective,
            priority=parent.priority,
            risk_level=parent.risk_level,
            parent_task_id=parent.id,
            created_by="alpha-coverage-director",
            input_contract=contract,
            expected_outputs=parent.expected_outputs,
            acceptance_criteria=parent.acceptance_criteria,
            approval_policy=deepcopy(parent.approval_policy)
            | {"coverage_successor_digest": proposal["successor_digest"]},
            approval_required=False,
            required_capabilities=parent.required_capabilities,
            allowed_machines=parent.allowed_machines,
            max_attempts=1,
        )
    )
    persist_new_task(db, task)
    _append_event(
        db,
        campaign,
        "coverage_successor_materialized",
        "alpha-coverage-director",
        {
            "parent_task_id": str(parent.id),
            "task_id": str(task.id),
            "plan_digest": task.plan_digest,
            "publication_digest": published.event_digest,
            "review_route_id": str(route.id),
            "capital_or_order_authority": False,
        },
    )
    return task, True
