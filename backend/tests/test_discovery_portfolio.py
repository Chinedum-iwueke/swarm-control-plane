from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from app.api.routes.discovery_portfolio import router
from app.models.discovery_portfolio import DiscoveryPortfolioCandidate
from app.schemas.discovery_portfolio import DiscoveryPortfolioCreate
from app.services import discovery_portfolio as service
from fastapi import HTTPException
from pydantic import ValidationError

DIGEST = "a" * 64


def candidate(key, domain, cluster, *, relevance=0.8, feasibility=0.8, cost=1):
    return {
        "candidate_key": key,
        "domain_key": domain,
        "cluster_key": cluster,
        "source_type": "discovery_map",
        "source_id": uuid4(),
        "source_digest": DIGEST,
        "question": f"Does the canonical {key} observation survive the declared controls?",
        "decision_relevance": relevance,
        "feasibility": feasibility,
        "attention_cost": cost,
    }


def request(candidates=None, policy=None, **updates):
    value = {
        "portfolio_key": "DISC009-PILOT",
        "version": "1.0.0",
        "project": "bulletproof-bt",
        "objective": "Allocate bounded research attention across independent inquiry domains.",
        "source_epoch": "2026-08-27T12:00:00Z",
        "policy": policy
        or {
            "attention_budget": 3,
            "maximum_selected": 3,
            "minimum_distinct_domains": 2,
            "maximum_per_domain": 2,
            "maximum_per_cluster": 1,
        },
        "candidates": candidates
        or [
            candidate("microstructure", "market-microstructure", "liquidity"),
            candidate("regime", "regime-analysis", "regimes"),
            candidate("costs", "market-microstructure", "costs"),
        ],
        "created_by": "disc009-pilot",
    }
    value.update(updates)
    return DiscoveryPortfolioCreate.model_validate(value)


def register(monkeypatch, payload, uncertainties=None):
    uncertainties = iter(uncertainties or [0.8] * len(payload.candidates))
    monkeypatch.setattr(
        service,
        "_source",
        lambda _db, item, _project, _epoch: (next(uncertainties), item.source_digest),
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    record = service.register_portfolio(db, payload)
    candidates = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], DiscoveryPortfolioCandidate)
    ]
    return record, candidates


def test_contract_rejects_duplicate_source_and_question():
    first = candidate("one", "domain-one", "cluster-one")
    duplicate = candidate("two", "domain-two", "cluster-two")
    duplicate["source_id"] = first["source_id"]
    with pytest.raises(ValidationError, match="canonical source"):
        request([first, duplicate])


def test_contract_rejects_impossible_domain_floor():
    with pytest.raises(ValidationError, match="cannot satisfy"):
        request(
            [
                candidate("one", "same-domain", "one"),
                candidate("two", "same-domain", "two"),
            ]
        )


def test_contract_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(ValidationError, match="sum to one"):
        request(
            policy={
                "attention_budget": 2,
                "maximum_selected": 2,
                "minimum_distinct_domains": 2,
                "maximum_per_domain": 1,
                "maximum_per_cluster": 1,
                "relevance_weight": 0.9,
                "feasibility_weight": 0.9,
                "novelty_weight": 0.9,
            }
        )


def test_future_source_epoch_fails_closed():
    with pytest.raises(HTTPException, match="future"):
        service.register_portfolio(
            MagicMock(), request(source_epoch="2999-01-01T00:00:00Z")
        )


def test_diversity_seed_prevents_high_score_monoculture(monkeypatch):
    payload = request(
        [
            candidate(
                "dominant-a", "domain-a", "cluster-a", relevance=1, feasibility=1
            ),
            candidate(
                "dominant-b", "domain-a", "cluster-b", relevance=0.99, feasibility=1
            ),
            candidate(
                "minority", "domain-b", "cluster-c", relevance=0.2, feasibility=0.2
            ),
        ]
    )
    record, items = register(monkeypatch, payload)
    selected = [item for item in items if item.selected]
    assert record.selected_count == 3
    assert {item.domain_key for item in selected} == {"domain-a", "domain-b"}


def test_domain_and_cluster_caps_retain_counterfactuals(monkeypatch):
    payload = request(
        [
            candidate("one", "domain-a", "shared"),
            candidate("two", "domain-a", "other"),
            candidate("three", "domain-b", "shared"),
            candidate("four", "domain-c", "four"),
        ],
        policy={
            "attention_budget": 4,
            "maximum_selected": 4,
            "minimum_distinct_domains": 2,
            "maximum_per_domain": 1,
            "maximum_per_cluster": 1,
        },
    )
    _, items = register(monkeypatch, payload)
    rejected = {
        item.candidate_key: item.decision["reason"]
        for item in items
        if not item.selected
    }
    assert set(rejected.values()) & {"domain_cap", "cluster_cap"}


def test_attention_budget_is_hard_and_explained(monkeypatch):
    payload = request(
        [
            candidate("one", "domain-a", "one", cost=2),
            candidate("two", "domain-b", "two", cost=2),
            candidate("three", "domain-c", "three", cost=2),
        ],
        policy={
            "attention_budget": 4,
            "maximum_selected": 3,
            "minimum_distinct_domains": 2,
            "maximum_per_domain": 1,
            "maximum_per_cluster": 1,
        },
    )
    record, items = register(monkeypatch, payload)
    assert record.attention_used == 4
    assert [item.decision["reason"] for item in items if not item.selected] == [
        "attention_budget"
    ]


def test_source_uncertainty_is_derived_not_caller_supplied(monkeypatch):
    payload = request()
    _, items = register(monkeypatch, payload, [0.1, 0.9, 0.2])
    scoring = {item.candidate_key: item.scoring for item in items}
    assert scoring["regime"]["source_uncertainty"] == 0.9
    assert "source_uncertainty" not in payload.candidates[0].model_fields_set


def test_same_sources_can_be_scheduled_in_a_new_version(monkeypatch):
    first, first_items = register(monkeypatch, request())
    second, second_items = register(monkeypatch, request(version="1.0.1"))
    assert first.allocation_digest != second.allocation_digest
    assert first_items[0].candidate_digest != second_items[0].candidate_digest


def test_source_failure_propagates_without_partial_allocation(monkeypatch):
    def fail(*_args):
        raise HTTPException(409, "source is stale")

    monkeypatch.setattr(service, "_source", fail)
    with pytest.raises(HTTPException, match="stale"):
        service.register_portfolio(MagicMock(), request())


def test_selection_audit_uncertainty_requires_complete_same_project_lineage():
    source_id = uuid4()
    evaluation_id = uuid4()
    plan_id = uuid4()
    map_id = uuid4()
    cycle_id = uuid4()
    program_id = uuid4()
    question = (
        "Does canonical opportunity evidence remain valid after selection correction?"
    )
    records = {
        source_id: SimpleNamespace(
            id=source_id,
            audit_digest=DIGEST,
            status="active",
            audited_at=datetime(2026, 8, 26, tzinfo=UTC),
            mechanism_evaluation_id=evaluation_id,
            conclusion="selection_risk_detected",
        ),
        evaluation_id: SimpleNamespace(
            id=evaluation_id, plan_id=plan_id, status="active"
        ),
        plan_id: SimpleNamespace(id=plan_id, discovery_map_id=map_id),
        map_id: SimpleNamespace(
            id=map_id,
            status="active",
            document={"source_daily_cycle_id": str(cycle_id), "question": question},
        ),
        cycle_id: SimpleNamespace(id=cycle_id, program_id=program_id),
        program_id: SimpleNamespace(id=program_id, project="bulletproof-bt"),
    }
    db = MagicMock()
    db.get.side_effect = lambda _model, identifier: records.get(UUID(str(identifier)))
    payload = (
        request()
        .candidates[0]
        .model_copy(
            update={
                "source_type": "selection_bias_audit",
                "source_id": source_id,
                "domain_key": "selection-bias",
                "question": "How should the selection-bias conclusion alter confidence in: "
                + question,
            }
        )
    )
    uncertainty, source_digest = service._source(
        db, payload, "bulletproof-bt", datetime(2026, 8, 27, tzinfo=UTC)
    )
    assert uncertainty == 0.8
    assert source_digest == DIGEST


def test_selection_audit_rejects_absent_canonical_source():
    payload = (
        request()
        .candidates[0]
        .model_copy(
            update={
                "source_type": "selection_bias_audit",
                "domain_key": "market-microstructure",
            }
        )
    )
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException, match="absent"):
        service._source(
            db, payload, "bulletproof-bt", datetime(2026, 8, 27, tzinfo=UTC)
        )


def test_active_mechanism_evaluation_derives_uncertainty_from_conclusion():
    source_id, plan_id, map_id, cycle_id, program_id = [uuid4() for _ in range(5)]
    question = "Does the opportunity survive rival mechanism tests?"
    records = {
        source_id: SimpleNamespace(
            id=source_id,
            evaluation_digest=DIGEST,
            status="active",
            evaluated_at=datetime(2026, 8, 26, tzinfo=UTC),
            plan_id=plan_id,
            conclusion="unresolved",
        ),
        plan_id: SimpleNamespace(id=plan_id, discovery_map_id=map_id),
        map_id: SimpleNamespace(
            id=map_id,
            status="active",
            document={"source_daily_cycle_id": str(cycle_id), "question": question},
        ),
        cycle_id: SimpleNamespace(id=cycle_id, program_id=program_id),
        program_id: SimpleNamespace(id=program_id, project="bulletproof-bt"),
    }
    db = MagicMock()
    db.get.side_effect = lambda _model, identifier: records.get(UUID(str(identifier)))
    payload = (
        request()
        .candidates[0]
        .model_copy(
            update={
                "source_type": "mechanism_evaluation",
                "source_id": source_id,
                "domain_key": "causal-reasoning",
                "question": "What uncertainty remains after mechanism evaluation for: "
                + question,
            }
        )
    )
    uncertainty, source_digest = service._source(
        db, payload, "bulletproof-bt", datetime(2026, 8, 27, tzinfo=UTC)
    )
    assert uncertainty == 0.8
    assert source_digest == DIGEST


def test_output_has_no_execution_or_capital_authority(monkeypatch):
    record, _ = register(monkeypatch, request())
    event = record.allocation_digest
    assert event
    assert not hasattr(record, "task_id")
    assert not hasattr(record, "capital_budget")


def test_route_surface_is_read_and_register_only():
    methods = {(route.path, tuple(sorted(route.methods))) for route in router.routes}
    assert ("/v1/research/discovery-portfolios", ("POST",)) in methods
    assert ("/v1/research/discovery-portfolios", ("GET",)) in methods
    assert all(
        "DELETE" not in route.methods and "PATCH" not in route.methods
        for route in router.routes
    )
