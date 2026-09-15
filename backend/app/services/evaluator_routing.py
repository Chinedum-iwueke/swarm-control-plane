from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, PackageDeployment, RolePackage
from app.models.evaluator_routing import (
    EvaluationIndependenceReceipt,
    EvaluationRoute,
    EvaluationRouteEvent,
    EvaluatorAssignment,
    EvaluatorProfile,
)
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.evaluator_routing import (
    AlphaStrategyReview,
    EvaluationRouteCreate,
    EvaluatorAssignmentComplete,
    EvaluatorProfileCreate,
)

CORRELATION_DIMENSIONS = ("machine", "provider", "model_family", "runtime")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def append_event(
    db: Session, route: EvaluationRoute, kind: str, actor: str, payload: dict
) -> EvaluationRouteEvent:
    previous = db.scalar(
        select(EvaluationRouteEvent)
        .where(EvaluationRouteEvent.route_id == route.id)
        .order_by(EvaluationRouteEvent.sequence.desc())
        .limit(1)
    )
    sequence = (previous.sequence if previous else 0) + 1
    previous_digest = previous.event_digest if previous else None
    event_digest = digest(
        {
            "route_id": str(route.id),
            "sequence": sequence,
            "event_type": kind,
            "actor": actor,
            "payload": payload,
            "previous_digest": previous_digest,
        }
    )
    event = EvaluationRouteEvent(
        route_id=route.id,
        sequence=sequence,
        event_type=kind,
        actor=actor,
        payload=payload,
        previous_digest=previous_digest,
        event_digest=event_digest,
    )
    db.add(event)
    db.flush()
    return event


def register_profile(db: Session, payload: EvaluatorProfileCreate) -> EvaluatorProfile:
    agent = db.get(Agent, payload.agent_id)
    if agent is None or not agent.is_enabled:
        raise HTTPException(409, "Evaluator agent is missing or disabled.")
    if not set(payload.capabilities).issubset(set(agent.capabilities)):
        raise HTTPException(
            409, "Evaluator capabilities exceed the agent registration."
        )
    deployment_row = db.execute(
        select(PackageDeployment, RolePackage)
        .join(RolePackage, RolePackage.id == PackageDeployment.package_id)
        .where(
            PackageDeployment.agent_id == agent.id,
            PackageDeployment.is_active.is_(True),
        )
    ).first()
    if deployment_row is None:
        raise HTTPException(409, "Evaluator lacks an active role-package deployment.")
    deployment, package = deployment_row
    runtime = (
        "/".join(filter(None, [agent.runtime, agent.runtime_version])) or "unknown"
    )
    document = {
        **payload.model_dump(mode="json"),
        "machine": agent.machine,
        "runtime": runtime,
        "package_id": str(package.id),
        "package_digest": package.manifest_digest,
    }
    profile = EvaluatorProfile(
        agent_id=agent.id,
        profile_version=payload.profile_version,
        status="active",
        review_kinds=payload.review_kinds,
        capabilities=payload.capabilities,
        machine=agent.machine,
        provider=payload.provider,
        model_family=payload.model_family,
        runtime=runtime,
        context_group=payload.context_group,
        package_id=package.id,
        package_digest=package.manifest_digest,
        attestation={
            "agent_slug": agent.slug,
            "deployment_id": str(deployment.id),
            "source_repository": package.source_repository,
            "source_commit": package.source_commit,
            "identity_claim_boundary": "provider and model family are operator-declared; agent, machine, runtime and package are registry-derived",
        },
        profile_digest=digest(document),
        registered_by=payload.registered_by,
    )
    for prior in db.scalars(
        select(EvaluatorProfile).where(
            EvaluatorProfile.agent_id == agent.id,
            EvaluatorProfile.status == "active",
        )
    ).all():
        prior.status = "retired"
        prior.retired_at = datetime.now(UTC)
    db.add(profile)
    db.flush()
    return profile


def _profile_identity(profile: EvaluatorProfile) -> dict:
    return {
        "agent_id": str(profile.agent_id),
        "machine": profile.machine,
        "provider": profile.provider,
        "model_family": profile.model_family,
        "runtime": profile.runtime,
        "context_group": profile.context_group,
        "package_digest": profile.package_digest,
        "profile_digest": profile.profile_digest,
    }


def producer_identity_for_lease(
    db: Session, agent: Agent, package_digests: list[str]
) -> dict | None:
    if not package_digests:
        return None
    profile = db.scalar(
        select(EvaluatorProfile)
        .where(
            EvaluatorProfile.agent_id == agent.id,
            EvaluatorProfile.status == "active",
            EvaluatorProfile.package_digest.in_(package_digests),
        )
        .order_by(EvaluatorProfile.created_at.desc())
        .limit(1)
    )
    if profile is None:
        return None
    runtime = (
        "/".join(filter(None, [agent.runtime, agent.runtime_version])) or "unknown"
    )
    if profile.machine != agent.machine or profile.runtime != runtime:
        return None
    return _profile_identity(profile)


def task_producer_identity(db: Session, task: Task) -> dict | None:
    event = db.scalar(
        select(TaskEvent)
        .where(
            TaskEvent.task_id == task.id,
            TaskEvent.event_type == "task_leased",
            TaskEvent.agent_id == task.assigned_agent_id,
            TaskEvent.attempt_number == task.attempt_count,
        )
        .order_by(TaskEvent.id.desc())
        .limit(1)
    )
    if event is None:
        return None
    identity = event.payload.get("producer_identity")
    if (
        not isinstance(identity, dict)
        or identity.get("agent_id") != str(task.assigned_agent_id)
        or event.payload.get("producer_identity_digest") != digest(identity)
    ):
        return None
    return identity


def _hard_conflicts(first: dict, second: dict) -> list[str]:
    conflicts = []
    for field in ("agent_id", "package_digest", "context_group"):
        if first.get(field) and first.get(field) == second.get(field):
            conflicts.append(field)
    return conflicts


def _correlation(first: dict, second: dict) -> dict:
    shared = [
        field
        for field in CORRELATION_DIMENSIONS
        if first.get(field) == second.get(field)
    ]
    return {
        "shared_dimensions": shared,
        "shared_dimension_count": len(shared),
        "hard_conflicts": _hard_conflicts(first, second),
    }


def _route_profiles(
    profiles: list[EvaluatorProfile], payload: EvaluationRouteCreate
) -> tuple[list[tuple[str, EvaluatorProfile, dict]], dict]:
    producer = payload.producer.model_dump(mode="json")
    required_caps = set(payload.required_capabilities)
    selected: list[tuple[str, EvaluatorProfile, dict]] = []
    excluded: list[dict] = []
    for review_kind in payload.required_review_kinds:
        eligible: list[tuple[int, str, EvaluatorProfile, dict]] = []
        for profile in profiles:
            identity = _profile_identity(profile)
            producer_corr = _correlation(producer, identity)
            reasons = list(producer_corr["hard_conflicts"])
            if review_kind not in profile.review_kinds:
                reasons.append("review_kind")
            if not required_caps.issubset(set(profile.capabilities)):
                reasons.append("capabilities")
            selected_corr = [
                _correlation(_profile_identity(item[1]), identity) for item in selected
            ]
            if any(item["hard_conflicts"] for item in selected_corr):
                reasons.append("selected_evaluator_hard_conflict")
            if any(
                item["shared_dimension_count"] > payload.max_pairwise_shared_dimensions
                for item in selected_corr
            ):
                reasons.append("pairwise_correlation_ceiling")
            if reasons:
                excluded.append(
                    {
                        "profile_digest": profile.profile_digest,
                        "review_kind": review_kind,
                        "reasons": sorted(set(reasons)),
                    }
                )
                continue
            score = producer_corr["shared_dimension_count"] + sum(
                item["shared_dimension_count"] for item in selected_corr
            )
            report = {
                "producer": producer_corr,
                "selected_evaluators": selected_corr,
                "correlation_score": score,
                "claim_boundary": "identity/package/context separation is enforced; shared provider/model/runtime/host dimensions are disclosed, not described as independent",
            }
            eligible.append((score, profile.profile_digest, profile, report))
        if not eligible:
            return [], {
                "category": "independent_evaluator_unavailable",
                "unfilled_review_kind": review_kind,
                "excluded": excluded[-50:],
            }
        _, _, chosen, report = min(eligible, key=lambda item: (item[0], item[1]))
        selected.append((review_kind, chosen, report))
    return selected, {}


def create_route(db: Session, payload: EvaluationRouteCreate) -> EvaluationRoute:
    document = payload.model_dump(mode="json")
    route = EvaluationRoute(
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        subject_digest=payload.subject_digest,
        producer=payload.producer.model_dump(mode="json"),
        policy={
            "required_review_kinds": payload.required_review_kinds,
            "required_capabilities": payload.required_capabilities,
            "max_pairwise_shared_dimensions": payload.max_pairwise_shared_dimensions,
            "hard_separation": ["agent_id", "package_digest", "context_group"],
            "disclosed_correlation": list(CORRELATION_DIMENSIONS),
        },
        status="routing",
        route_digest=digest(document),
        requested_by=payload.requested_by,
        blocked_reason={},
    )
    db.add(route)
    db.flush()
    append_event(
        db,
        route,
        "route_requested",
        payload.requested_by,
        {"route_digest": route.route_digest, "subject_digest": route.subject_digest},
    )
    profiles = list(
        db.scalars(
            select(EvaluatorProfile)
            .where(EvaluatorProfile.status == "active")
            .order_by(EvaluatorProfile.profile_digest)
        ).all()
    )
    selected, blocked = _route_profiles(profiles, payload)
    if blocked:
        route.status = "blocked"
        route.blocked_reason = blocked
        append_event(db, route, "route_blocked", "evaluator-router", blocked)
        return route
    for review_kind, profile, report in selected:
        assignment_document = {
            "route_digest": route.route_digest,
            "review_kind": review_kind,
            "evaluator_profile_digest": profile.profile_digest,
            "correlation_report": report,
        }
        assignment = EvaluatorAssignment(
            route_id=route.id,
            evaluator_profile_id=profile.id,
            review_kind=review_kind,
            status="assigned",
            correlation_report=report,
            assignment_digest=digest(assignment_document),
        )
        db.add(assignment)
        db.flush()
        append_event(
            db,
            route,
            "evaluator_assigned",
            "evaluator-router",
            {
                "review_kind": review_kind,
                "profile_digest": profile.profile_digest,
                "assignment_digest": assignment.assignment_digest,
                "correlation_report": report,
            },
        )
    route.status = "assigned"
    return route


def complete_assignment(
    db: Session,
    route: EvaluationRoute,
    assignment: EvaluatorAssignment,
    payload: EvaluatorAssignmentComplete,
) -> None:
    if route.status != "assigned" or assignment.status != "assigned":
        raise HTTPException(409, "Only an active assigned evaluation can be completed.")
    profile = db.get(EvaluatorProfile, assignment.evaluator_profile_id)
    if profile is None or profile.agent_id != payload.evaluator_agent_id:
        raise HTTPException(
            403, "Only the routed evaluator may complete this assignment."
        )
    review = None
    if route.subject_type == "alpha_strategy_qualification":
        review = payload.alpha_strategy_review
        if review is None:
            raise HTTPException(
                422, "Alpha strategy evaluation requires an explicit review verdict."
            )
        if review.subject_digest != route.subject_digest:
            raise HTTPException(
                422, "Alpha strategy review identifies a different subject."
            )
        if digest(review.model_dump(mode="json")) != payload.review_digest:
            raise HTTPException(
                422, "Alpha strategy review digest does not match its content."
            )
    assignment.status = "completed"
    assignment.review_id = payload.review_id
    assignment.review_digest = payload.review_digest
    assignment.completed_by = str(payload.evaluator_agent_id)
    assignment.completed_at = datetime.now(UTC)
    append_event(
        db,
        route,
        "evaluation_completed",
        str(payload.evaluator_agent_id),
        {
            "assignment_digest": assignment.assignment_digest,
            "review_kind": assignment.review_kind,
            "review_id": payload.review_id,
            "review_digest": payload.review_digest,
            **(
                {"alpha_strategy_review": review.model_dump(mode="json")}
                if review
                else {}
            ),
        },
    )
    assignments = list(
        db.scalars(
            select(EvaluatorAssignment).where(EvaluatorAssignment.route_id == route.id)
        ).all()
    )
    if all(item.status == "completed" for item in assignments):
        _issue_receipt(db, route, assignments)


def _issue_receipt(
    db: Session, route: EvaluationRoute, assignments: list[EvaluatorAssignment]
) -> EvaluationIndependenceReceipt:
    existing = db.scalar(
        select(EvaluationIndependenceReceipt).where(
            EvaluationIndependenceReceipt.route_id == route.id
        )
    )
    if existing:
        return existing
    assertion = {
        "schema_version": "evaluation-independence-assertion-v1.0.0",
        "route_digest": route.route_digest,
        "subject_digest": route.subject_digest,
        "producer": route.producer,
        "policy": route.policy,
        "assignments": [
            {
                "assignment_digest": item.assignment_digest,
                "review_kind": item.review_kind,
                "review_digest": item.review_digest,
                "correlation_report": item.correlation_report,
            }
            for item in sorted(assignments, key=lambda value: value.review_kind)
        ],
        "claim_boundary": "independence demonstrated under declared identity/package/context rules; disclosed shared runtime dimensions remain correlated risk",
    }
    if route.subject_type == "alpha_strategy_qualification":
        for item, document in zip(
            sorted(assignments, key=lambda value: value.review_kind),
            assertion["assignments"],
        ):
            profile = db.get(EvaluatorProfile, item.evaluator_profile_id)
            event = db.scalar(
                select(EvaluationRouteEvent).where(
                    EvaluationRouteEvent.route_id == route.id,
                    EvaluationRouteEvent.event_type == "evaluation_completed",
                    EvaluationRouteEvent.actor == item.completed_by,
                    EvaluationRouteEvent.payload["assignment_digest"].astext
                    == item.assignment_digest,
                )
            )
            if profile is None or event is None:
                raise HTTPException(
                    409, "Alpha review lacks immutable evaluator provenance."
                )
            document["evaluator_identity"] = _profile_identity(profile)
            document["alpha_strategy_review"] = event.payload["alpha_strategy_review"]
    receipt = EvaluationIndependenceReceipt(
        route_id=route.id,
        subject_digest=route.subject_digest,
        verdict="independence_demonstrated",
        assertion=assertion,
        receipt_digest=digest(assertion),
        issued_by="evaluator-router",
    )
    db.add(receipt)
    route.status = "completed"
    route.completed_at = datetime.now(UTC)
    append_event(
        db,
        route,
        "independence_asserted",
        "evaluator-router",
        {"verdict": receipt.verdict, "receipt_digest": receipt.receipt_digest},
    )
    db.flush()
    return receipt


def require_independence(
    db: Session, route: EvaluationRoute
) -> EvaluationIndependenceReceipt:
    receipt = db.scalar(
        select(EvaluationIndependenceReceipt).where(
            EvaluationIndependenceReceipt.route_id == route.id
        )
    )
    if route.status != "completed" or receipt is None:
        raise HTTPException(
            409,
            "Independent evaluation is incomplete; promotion must remain blocked.",
        )
    return receipt


def alpha_strategy_reviews_approved(
    db: Session,
    route: EvaluationRoute,
    *,
    subject_digest: str,
    producer_agent_id,
    excluded_agent_ids=(),
    excluded_identities=(),
    qualifier_identity=None,
) -> bool:
    """Require both routed independence and immutable approving review content."""
    if (
        route.subject_type != "alpha_strategy_qualification"
        or route.subject_digest != subject_digest
        or route.status != "completed"
        or str(route.producer.get("agent_id")) != str(producer_agent_id)
        or producer_agent_id is None
        or not {"strategy_spec", "causality_leakage"}.issubset(
            set(route.policy.get("required_review_kinds", []))
        )
    ):
        return False
    if qualifier_identity is not None:
        if qualifier_identity not in excluded_identities or any(
            qualifier_identity.get(key) != route.producer.get(key)
            for key in (
                "agent_id",
                "package_digest",
                "context_group",
                "machine",
                "provider",
                "model_family",
                "runtime",
            )
        ):
            return False
    receipt = db.scalar(
        select(EvaluationIndependenceReceipt).where(
            EvaluationIndependenceReceipt.route_id == route.id
        )
    )
    if (
        receipt is None
        or receipt.subject_digest != subject_digest
        or receipt.verdict != "independence_demonstrated"
        or receipt.receipt_digest != digest(receipt.assertion)
        or receipt.assertion.get("route_digest") != route.route_digest
        or receipt.assertion.get("subject_digest") != subject_digest
        or receipt.assertion.get("producer") != route.producer
        or receipt.assertion.get("policy") != route.policy
    ):
        return False
    assignments = list(
        db.scalars(
            select(EvaluatorAssignment).where(EvaluatorAssignment.route_id == route.id)
        ).all()
    )
    events = list(
        db.scalars(
            select(EvaluationRouteEvent).where(
                EvaluationRouteEvent.route_id == route.id,
                EvaluationRouteEvent.event_type == "evaluation_completed",
            )
        ).all()
    )
    required = set(route.policy["required_review_kinds"])
    if {item.review_kind for item in assignments} != required:
        return False
    asserted = receipt.assertion.get("assignments")
    if not isinstance(asserted, list) or len(asserted) != len(assignments):
        return False
    reviewed_identities = []
    for assignment in assignments:
        profile = db.get(EvaluatorProfile, assignment.evaluator_profile_id)
        matching = [
            event
            for event in events
            if (
                event.payload.get("assignment_digest") == assignment.assignment_digest
                and event.payload.get("review_digest") == assignment.review_digest
                and event.actor == assignment.completed_by
            )
        ]
        if (
            assignment.status != "completed"
            or profile is None
            or str(profile.agent_id) != assignment.completed_by
            or str(profile.agent_id)
            in {str(producer_agent_id), *(str(actor) for actor in excluded_agent_ids)}
            or len(matching) != 1
        ):
            return False
        identity = _profile_identity(profile)
        for other in (route.producer, *excluded_identities, *reviewed_identities):
            if _hard_conflicts(identity, other):
                return False
            if _correlation(identity, other)[
                "shared_dimension_count"
            ] > route.policy.get("max_pairwise_shared_dimensions", 4):
                return False
        reviewed_identities.append(identity)
        try:
            review = AlphaStrategyReview.model_validate(
                matching[0].payload.get("alpha_strategy_review")
            )
        except ValueError:
            return False
        if (
            review.subject_digest != subject_digest
            or review.verdict != "approve"
            or digest(review.model_dump(mode="json")) != assignment.review_digest
        ):
            return False
        attested = [
            item
            for item in asserted
            if (
                item.get("assignment_digest") == assignment.assignment_digest
                and item.get("review_kind") == assignment.review_kind
                and item.get("review_digest") == assignment.review_digest
                and item.get("alpha_strategy_review") == review.model_dump(mode="json")
                and item.get("evaluator_identity") == _profile_identity(profile)
            )
        ]
        if len(attested) != 1:
            return False
    return bool(assignments)


def serialize_route(db: Session, route: EvaluationRoute) -> dict:
    assignments = list(
        db.scalars(
            select(EvaluatorAssignment)
            .where(EvaluatorAssignment.route_id == route.id)
            .order_by(EvaluatorAssignment.review_kind)
        ).all()
    )
    events = list(
        db.scalars(
            select(EvaluationRouteEvent)
            .where(EvaluationRouteEvent.route_id == route.id)
            .order_by(EvaluationRouteEvent.sequence)
        ).all()
    )
    receipt = db.scalar(
        select(EvaluationIndependenceReceipt).where(
            EvaluationIndependenceReceipt.route_id == route.id
        )
    )
    return {
        "id": route.id,
        "subject_type": route.subject_type,
        "subject_id": route.subject_id,
        "subject_digest": route.subject_digest,
        "producer": route.producer,
        "policy": route.policy,
        "status": route.status,
        "route_digest": route.route_digest,
        "requested_by": route.requested_by,
        "blocked_reason": route.blocked_reason,
        "created_at": route.created_at,
        "completed_at": route.completed_at,
        "assignments": [
            {
                "id": str(item.id),
                "evaluator_profile_id": str(item.evaluator_profile_id),
                "review_kind": item.review_kind,
                "status": item.status,
                "correlation_report": item.correlation_report,
                "assignment_digest": item.assignment_digest,
                "review_id": item.review_id,
                "review_digest": item.review_digest,
            }
            for item in assignments
        ],
        "events": [
            {
                "sequence": item.sequence,
                "event_type": item.event_type,
                "actor": item.actor,
                "payload": item.payload,
                "event_digest": item.event_digest,
            }
            for item in events
        ],
        "independence_receipt": (
            {
                "id": str(receipt.id),
                "verdict": receipt.verdict,
                "assertion": receipt.assertion,
                "receipt_digest": receipt.receipt_digest,
            }
            if receipt
            else None
        ),
    }
