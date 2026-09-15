import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.evaluator_routing import (
    AlphaStrategyReview,
    EvaluationRouteCreate,
    EvaluatorAssignmentComplete,
)
from app.services.evaluator_routing import (
    _correlation,
    _profile_identity,
    _route_profiles,
    alpha_strategy_reviews_approved,
    complete_assignment,
    digest,
    producer_identity_for_lease,
    require_independence,
    task_producer_identity,
)
from fastapi import HTTPException

ONE = uuid.UUID("10000000-0000-4000-8000-000000000001")
TWO = uuid.UUID("20000000-0000-4000-8000-000000000002")
THREE = uuid.UUID("30000000-0000-4000-8000-000000000003")
DIGEST = "a" * 64


def alpha_review_fixture():
    subject = DIGEST
    record = SimpleNamespace(
        id=uuid.uuid4(),
        subject_type="alpha_strategy_qualification",
        subject_digest=subject,
        status="completed",
        producer={"agent_id": str(ONE)},
        policy={"required_review_kinds": ["strategy_spec", "causality_leakage"]},
        route_digest="b" * 64,
    )
    assignments, events, profiles = [], [], {}
    for index, (kind, actor) in enumerate(
        zip(record.policy["required_review_kinds"], (TWO, THREE))
    ):
        review = AlphaStrategyReview(
            subject_digest=subject,
            verdict="approve",
            rationale="Reviewed causal timing and exact native implementation.",
            checks=["closed bars", "next-bar execution"],
        ).model_dump(mode="json")
        item = SimpleNamespace(
            evaluator_profile_id=uuid.uuid4(),
            review_kind=kind,
            status="completed",
            assignment_digest=str(index) * 64,
            review_digest=digest(review),
            completed_by=str(actor),
        )
        profiles[item.evaluator_profile_id] = profile(
            actor, str(index + 3) * 64, f"review-context-{index}", kind
        )
        assignments.append(item)
        events.append(
            SimpleNamespace(
                actor=str(actor),
                payload={
                    "assignment_digest": item.assignment_digest,
                    "review_digest": item.review_digest,
                    "alpha_strategy_review": review,
                },
            )
        )
    assertion = {
        "route_digest": record.route_digest,
        "subject_digest": subject,
        "producer": record.producer,
        "policy": record.policy,
        "assignments": [
            {
                "assignment_digest": item.assignment_digest,
                "review_kind": item.review_kind,
                "review_digest": item.review_digest,
                "evaluator_identity": _profile_identity(
                    profiles[item.evaluator_profile_id]
                ),
                "alpha_strategy_review": event.payload["alpha_strategy_review"],
            }
            for item, event in zip(assignments, events)
        ],
    }
    receipt = SimpleNamespace(
        subject_digest=subject,
        verdict="independence_demonstrated",
        assertion=assertion,
        receipt_digest=digest(assertion),
    )
    db = MagicMock()
    db.scalar.return_value = receipt
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: assignments),
        SimpleNamespace(all=lambda: events),
    ]
    db.get.side_effect = lambda model, key: profiles[key]
    return db, record, receipt, assignments, events


def test_alpha_review_requires_real_approving_content():
    db, record, _, _, _ = alpha_review_fixture()
    assert alpha_strategy_reviews_approved(
        db, record, subject_digest=DIGEST, producer_agent_id=ONE
    )


def test_original_drafter_cannot_review_on_another_executor_slot():
    db, record, _, _, _ = alpha_review_fixture()
    assert not alpha_strategy_reviews_approved(
        db,
        record,
        subject_digest=DIGEST,
        producer_agent_id=ONE,
        excluded_agent_ids=[TWO],
    )


def test_same_agent_package_rollover_keeps_qualifier_as_primary():
    db, record, _, _, _ = alpha_review_fixture()
    qualifier = dict(record.producer)
    drafter = dict(qualifier, package_digest="9" * 64, context_group="old-draft")
    assert alpha_strategy_reviews_approved(
        db, record, subject_digest=DIGEST, producer_agent_id=ONE,
        excluded_identities=[drafter, qualifier], qualifier_identity=qualifier,
    )


def test_drafter_package_or_context_is_excluded_even_for_a_different_agent():
    db, record, receipt, _, _ = alpha_review_fixture()
    identity = dict(receipt.assertion["assignments"][0]["evaluator_identity"])
    identity["agent_id"] = str(uuid.uuid4())
    assert not alpha_strategy_reviews_approved(
        db,
        record,
        subject_digest=DIGEST,
        producer_agent_id=ONE,
        excluded_identities=[identity],
    )


def test_producer_profile_is_frozen_from_authorized_package_at_lease():
    db = MagicMock()
    actual = profile(ONE, "b" * 64, "producer-context", "producer_identity")
    db.scalar.return_value = actual
    agent = SimpleNamespace(
        id=ONE, machine=actual.machine, runtime="codex-cli", runtime_version="pinned"
    )
    assert producer_identity_for_lease(
        db, agent, [actual.package_digest]
    ) == _profile_identity(actual)
    agent.runtime_version = "different"
    assert producer_identity_for_lease(db, agent, [actual.package_digest]) is None
    assert producer_identity_for_lease(db, agent, []) is None


def test_historical_producer_identity_is_not_inferred_from_current_registration():
    db = MagicMock()
    task = SimpleNamespace(id=uuid.uuid4(), assigned_agent_id=ONE, attempt_count=1)
    db.scalar.return_value = None
    assert task_producer_identity(db, task) is None
    identity = _profile_identity(
        profile(ONE, "b" * 64, "producer-context", "producer_identity")
    )
    event = SimpleNamespace(
        payload={
            "producer_identity": identity,
            "producer_identity_digest": digest(identity),
        }
    )
    db.scalar.return_value = event
    assert task_producer_identity(db, task) == identity
    identity["context_group"] = "changed"
    assert task_producer_identity(db, task) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "subject",
        "producer",
        "receipt",
        "pending",
        "missing",
        "reject",
        "content",
        "self",
    ],
)
def test_alpha_review_gate_rejects_unbound_or_nonapproving_evidence(mutation):
    db, record, receipt, assignments, events = alpha_review_fixture()
    if mutation == "subject":
        record.subject_digest = "c" * 64
    elif mutation == "producer":
        record.producer["agent_id"] = str(TWO)
    elif mutation == "receipt":
        receipt.receipt_digest = "c" * 64
    elif mutation == "pending":
        assignments[0].status = "assigned"
    elif mutation == "missing":
        events[0].payload.pop("alpha_strategy_review")
    elif mutation == "reject":
        review = events[0].payload["alpha_strategy_review"]
        review["verdict"] = "reject"
        assignments[0].review_digest = digest(review)
        events[0].payload["review_digest"] = assignments[0].review_digest
    elif mutation == "content":
        events[0].payload["alpha_strategy_review"]["checks"] = ["altered"]
    else:
        db.get.side_effect = lambda model, key: SimpleNamespace(agent_id=ONE)
    assert not alpha_strategy_reviews_approved(
        db, record, subject_digest=DIGEST, producer_agent_id=ONE
    )


@pytest.mark.parametrize("mutation", ["missing", "subject", "digest"])
def test_alpha_assignment_completion_validates_review_before_mutation(mutation):
    db = MagicMock()
    db.get.return_value = SimpleNamespace(agent_id=TWO)
    record = SimpleNamespace(
        status="assigned",
        subject_type="alpha_strategy_qualification",
        subject_digest=DIGEST,
    )
    assignment = SimpleNamespace(status="assigned", evaluator_profile_id=uuid.uuid4())
    review = AlphaStrategyReview(
        subject_digest="c" * 64 if mutation == "subject" else DIGEST,
        verdict="approve",
        rationale="Independent specification review completed.",
        checks=["causality"],
    )
    payload = EvaluatorAssignmentComplete(
        evaluator_agent_id=TWO,
        review_id="review-1",
        review_digest="d" * 64
        if mutation == "digest"
        else digest(review.model_dump(mode="json")),
        alpha_strategy_review=None if mutation == "missing" else review,
    )
    with pytest.raises(HTTPException) as error:
        complete_assignment(db, record, assignment, payload)
    assert error.value.status_code == 422
    assert assignment.status == "assigned"


def profile(
    agent_id: uuid.UUID,
    package: str,
    context: str,
    kind: str,
    *,
    machine: str = "vm1-developer",
    provider: str = "openai",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=agent_id,
        review_kinds=[kind],
        capabilities=["independent-review"],
        machine=machine,
        provider=provider,
        model_family="codex",
        runtime="codex-cli/pinned",
        context_group=context,
        package_digest=package,
        profile_digest=str(agent_id).replace("-", "") * 2,
    )


def route(**overrides) -> EvaluationRouteCreate:
    value = {
        "subject_type": "research_result",
        "subject_id": "result-1",
        "subject_digest": DIGEST,
        "producer": {
            "actor": "producer",
            "agent_id": str(ONE),
            "machine": "vm1-developer",
            "provider": "openai",
            "model_family": "codex",
            "runtime": "codex-cli/pinned",
            "context_group": "producer-context",
            "package_digest": "b" * 64,
        },
        "required_review_kinds": ["statistical", "adversarial"],
        "required_capabilities": ["independent-review"],
        "max_pairwise_shared_dimensions": 4,
        "requested_by": "research-orchestrator",
    }
    value.update(overrides)
    return EvaluationRouteCreate.model_validate(value)


def test_correlation_separates_hard_conflicts_from_disclosed_runtime_risk() -> None:
    first = {
        "agent_id": "a",
        "package_digest": "p1",
        "context_group": "c1",
        "machine": "vm1",
        "provider": "openai",
        "model_family": "codex",
        "runtime": "cli",
    }
    second = {**first, "agent_id": "b", "package_digest": "p2", "context_group": "c2"}
    report = _correlation(first, second)
    assert report["hard_conflicts"] == []
    assert report["shared_dimension_count"] == 4


def test_router_selects_distinct_packages_agents_and_contexts() -> None:
    statistical = profile(TWO, "c" * 64, "stat-context", "statistical")
    adversarial = profile(THREE, "d" * 64, "adv-context", "adversarial")
    selected, blocked = _route_profiles([statistical, adversarial], route())
    assert blocked == {}
    assert [item[0] for item in selected] == ["statistical", "adversarial"]
    assert len({item[1].agent_id for item in selected}) == 2
    assert selected[1][2]["selected_evaluators"][0]["shared_dimension_count"] == 4


def test_router_blocks_self_review_and_unavailable_independence() -> None:
    same = profile(ONE, "b" * 64, "producer-context", "statistical")
    selected, blocked = _route_profiles([same], route())
    assert selected == []
    assert blocked["category"] == "independent_evaluator_unavailable"
    assert {"agent_id", "package_digest", "context_group"}.issubset(
        blocked["excluded"][0]["reasons"]
    )


def test_router_enforces_pairwise_correlation_ceiling() -> None:
    profiles = [
        profile(TWO, "c" * 64, "stat-context", "statistical"),
        profile(THREE, "d" * 64, "adv-context", "adversarial"),
    ]
    selected, blocked = _route_profiles(
        profiles, route(max_pairwise_shared_dimensions=0)
    )
    assert selected == []
    assert blocked["unfilled_review_kind"] == "adversarial"


def test_only_routed_agent_can_complete_assignment() -> None:
    db = MagicMock()
    db.get.return_value = SimpleNamespace(agent_id=TWO)
    record = SimpleNamespace(status="assigned")
    assignment = SimpleNamespace(
        id=uuid.uuid4(),
        evaluator_profile_id=uuid.uuid4(),
        status="assigned",
        assignment_digest=DIGEST,
        review_kind="statistical",
    )
    payload = SimpleNamespace(
        evaluator_agent_id=THREE, review_id="review-1", review_digest=DIGEST
    )
    with pytest.raises(HTTPException, match="routed evaluator"):
        complete_assignment(db, record, assignment, payload)


def test_incomplete_route_blocks_promotion_assertion() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException, match="promotion must remain blocked"):
        require_independence(db, SimpleNamespace(id=uuid.uuid4(), status="assigned"))
