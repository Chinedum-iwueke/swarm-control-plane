import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.evaluator_routing import EvaluationRouteCreate
from app.services.evaluator_routing import (
    _correlation,
    _route_profiles,
    complete_assignment,
    require_independence,
)

ONE = uuid.UUID("10000000-0000-4000-8000-000000000001")
TWO = uuid.UUID("20000000-0000-4000-8000-000000000002")
THREE = uuid.UUID("30000000-0000-4000-8000-000000000003")
DIGEST = "a" * 64


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
