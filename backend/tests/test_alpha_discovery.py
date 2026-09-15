from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.schemas.alpha_campaign import AlphaCampaignCreate
from app.schemas.alpha_discovery import (
    AlphaFounderResearchIdeaCreate,
    AlphaPredictiveCandidate,
    AlphaResearchMandateCreate,
)
from app.services.alpha_discovery import (
    _bounded_context,
    _candidate_reasons,
    _discovery_corpus,
    _discovery_queries,
    _recover_resumed_stage,
    recover_discovery_grounding,
)
from fastapi import HTTPException
from pydantic import ValidationError

DIGEST = "a" * 64
COMMIT = "b" * 40


def test_discovery_context_carries_frozen_execution_constraints(monkeypatch):
    mandate = SimpleNamespace(
        objective="Discover mechanisms.",
        mandate_digest=DIGEST,
        specification={
            "execution_window_start": "2025-05-01T00:00:00Z",
            "execution_window_end": "2026-05-01T00:00:00Z",
            "bulletproof_source_commit": COMMIT,
            "minimum_liquidity_usd": 100_000,
        },
        budget={"maximum_variants_per_hypothesis": 8},
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(
        "app.services.alpha_discovery._discovery_corpus",
        lambda db, mandate: {"citations": []},
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery._dataset_inventory", lambda mandate: []
    )
    catalog = {
        "status": "cataloged_pending_quality",
        "assets": [["perp", "binance", "ETHUSDT"], ["perp", "bybit", "SOLUSDT"]],
        "receipt_digest": DIGEST,
        "execution_authority": False,
    }
    monkeypatch.setattr(
        "app.services.alpha_discovery.lake_inventory_summary", lambda db: catalog
    )
    context = _bounded_context(db, mandate)
    assert context["lake_catalog"] == catalog
    assert context["datasets"] == []
    value, _ = candidate()
    value.data.instrument = "ETHUSDT"
    reasons, binding = _candidate_reasons(
        value, SimpleNamespace(context=context), mandate, []
    )
    assert "data002_003_availability_not_demonstrated" in reasons
    assert binding is None
    constraints = context["research_constraints"]
    assert constraints["maximum_variants_per_hypothesis"] == 8
    assert constraints["minimum_liquidity_usd"] == 100_000
    assert "quote_volume" in constraints["liquidity_measurement_fields"]
    assert constraints["historical_group_labels_are_not_mandatory_universes"]
    assert (
        constraints["execution_window_start"]
        == mandate.specification["execution_window_start"]
    )
    assert constraints["bulletproof_source_commit"] == COMMIT
    assert constraints["new_code_requires_explicit_approval"]
    assert constraints["catalog_visibility_is_not_execution_admission"]
    assert not constraints["capital_or_order_authority"]
    assert "verification_receipt" in context["equation_policy"]["campaign_use_requires"]


def test_founder_universe_hints_default_to_all_eligible_without_expanding_mandate():
    payload = AlphaFounderResearchIdeaCreate(
        mandate_id=uuid4(), expected_mandate_digest=DIGEST,
        idea="Does cross-asset liquidity predict future residual returns?",
        submitted_by="founder-operator",
    )
    assert payload.universe_slices == ["all_eligible"]
    assert payload.universe_selection_policy == "preregistered_point_in_time"
    legacy = payload.model_copy(update={"universe_slices": ["stable", "volatile"]})
    assert legacy.universe_slices == ["stable", "volatile"]


@pytest.mark.parametrize(
    "condition",
    ["valid", "expired", "changed", "running", "grounded", "exhausted", "empty"],
)
def test_grounding_recovery_preserves_old_cycle_and_approval(monkeypatch, condition):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(
        id=uuid4(),
        status="active",
        valid_from=moment - timedelta(days=1),
        valid_until=moment + timedelta(days=1),
        mandate_digest=DIGEST,
        cycle_count=1,
        hypothesis_count=0,
        trial_count=0,
        budget={
            "maximum_cycles": 42,
            "maximum_hypotheses": 100,
            "maximum_total_trials": 500,
        },
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        status="completed",
        campaign_id=None,
        context={"research_intelligence": {"citations": []}},
        intelligence_task_id=None,
        hypothesis_task_id=None,
        cycle_digest="d" * 64,
    )
    payload = SimpleNamespace(
        expected_mandate_digest=DIGEST,
        expected_cycle_id=cycle.id,
        actor="founder-operator",
        reason="Recover empty frozen grounding after verified retrieval repair.",
    )
    if condition == "expired":
        mandate.valid_until = moment - timedelta(seconds=1)
    if condition == "changed":
        payload.expected_cycle_id = uuid4()
    if condition == "running":
        cycle.status = "running"
    if condition == "grounded":
        cycle.context["research_intelligence"]["citations"] = [
            {"object_id": str(uuid4())}
        ]
    if condition == "exhausted":
        mandate.cycle_count = 42
    db = MagicMock()
    db.scalar.side_effect = [cycle, None]
    context = {
        "research_intelligence": {
            "citations": [] if condition == "empty" else [{"object_id": str(uuid4())}]
        }
    }
    monkeypatch.setattr(
        "app.services.alpha_discovery._bounded_context", lambda db, mandate: context
    )
    new_cycle = MagicMock(
        return_value=SimpleNamespace(
            id=uuid4(), status="running", cycle_digest="e" * 64
        )
    )
    monkeypatch.setattr("app.services.alpha_discovery._new_cycle", new_cycle)
    event = MagicMock()
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    if condition == "valid":
        result = recover_discovery_grounding(db, mandate, payload)
        assert result.id != cycle.id
        assert cycle.status == "completed"
        assert cycle.context["research_intelligence"]["citations"] == []
        assert mandate.mandate_digest == DIGEST
        assert event.call_args.args[2] == "ungrounded_discovery_recovered_by_operator"
        assert new_cycle.call_args.kwargs["prepared_context"] is context
    else:
        with pytest.raises(HTTPException) as error:
            recover_discovery_grounding(db, mandate, payload)
        assert error.value.status_code == 409
        new_cycle.assert_not_called()
        event.assert_not_called()


def test_discovery_query_plan_is_bounded_data_aware_and_rotates():
    mandate = SimpleNamespace(
        objective="Discover predictive mechanisms on admitted data.",
        cycle_count=0,
        specification={
            "dataset_bindings": [{"output_columns": ["close", "high", "low", "volume"]}]
        },
    )
    first = _discovery_queries(mandate)
    assert len(first) == 4
    assert "momentum transaction costs" in first
    assert all("funding" not in q for q in first)
    mandate.cycle_count = 3
    assert _discovery_queries(mandate) != first


def test_discovery_grounding_keeps_provenance_and_deduplicates(monkeypatch):
    mandate = SimpleNamespace(
        objective="Discover mechanisms.",
        cycle_count=0,
        specification={"dataset_bindings": [{"output_columns": ["close"]}]},
    )
    object_id = uuid4()
    calls = []

    def search(db, request, access):
        calls.append(request)
        hits = (
            []
            if len(calls) == 1
            else [
                {
                    "object_id": object_id,
                    "text": "Cited predictive mechanism.",
                    "confidence": 0.7,
                    "citation": {"content_digest": DIGEST, "coordinates": {}},
                }
            ]
        )
        return {
            "corpus_digest": DIGEST,
            "abstained": not hits,
            "hits": hits,
            "confidence": 0.7 if hits else 0,
        }

    monkeypatch.setattr("app.services.alpha_discovery.hybrid_search", search)
    corpus = _discovery_corpus(MagicMock(), mandate)
    assert not corpus["abstained"]
    assert len(corpus["citations"]) == 1
    assert len(corpus["citations"][0]["retrieved_for"]) == 2
    assert len(corpus["query_receipts"]) == 3
    assert all(request.limit == 6 for request in calls)


def test_discovery_grounding_rejects_mixed_corpus_epochs(monkeypatch):
    mandate = SimpleNamespace(
        objective="Discover mechanisms.",
        cycle_count=0,
        specification={"dataset_bindings": [{"output_columns": ["close"]}]},
    )
    search = MagicMock(
        side_effect=[
            {"corpus_digest": DIGEST, "abstained": True, "hits": [], "confidence": 0},
            {"corpus_digest": "c" * 64, "abstained": True, "hits": [], "confidence": 0},
        ]
    )
    monkeypatch.setattr("app.services.alpha_discovery.hybrid_search", search)
    corpus = _discovery_corpus(MagicMock(), mandate)
    assert corpus["abstained"]
    assert corpus["citations"] == []
    assert "Corpus changed" in corpus["error"]


@pytest.mark.parametrize("condition", ["valid", "missing", "stale", "wrong_digest"])
def test_stage_recovery_requires_later_bound_operator_resume(monkeypatch, condition):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(id=uuid4(), mandate_digest=DIGEST)
    cycle = SimpleNamespace(
        id=uuid4(),
        status="needs_attention",
        phase="intelligence_synthesis",
        campaign_id=None,
        intelligence_task_id=uuid4(),
        completed_at=moment,
    )
    task = SimpleNamespace(
        id=cycle.intelligence_task_id,
        status="queued",
        input_contract={
            "cycle_id": str(cycle.id),
            "mandate_id": str(mandate.id),
            "mandate_digest": DIGEST,
            "stage": "intelligence",
        },
    )
    if condition == "wrong_digest":
        task.input_contract["mandate_digest"] = "c" * 64
    failed = SimpleNamespace(created_at=moment)
    resumed = (
        None
        if condition == "missing"
        else SimpleNamespace(
            id=42,
            created_at=moment + timedelta(seconds=-1 if condition == "stale" else 1),
            payload={"requested_by": "founder-operator"},
        )
    )
    db = MagicMock()
    db.get.return_value = task
    db.scalar.side_effect = [failed, resumed]
    event = MagicMock()
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    assert _recover_resumed_stage(db, mandate, cycle) is (condition == "valid")
    if condition == "valid":
        assert cycle.status == "running"
        assert cycle.completed_at is None
        assert event.call_args.args[2] == "discovery_stage_resumed_by_operator"
    else:
        assert cycle.status == "needs_attention"
        event.assert_not_called()


def binding():
    return {
        "dataset_build_id": uuid4(),
        "catalog_id": uuid4(),
        "lake_governance_snapshot_id": uuid4(),
        "producer_receipt_id": uuid4(),
        "dataset_key": "bybit-btcusdt-perp-1m",
        "partition_digests": [DIGEST],
        "evidence_class": "live_exchange_history",
        "research_principal": "alpha-research-runner",
    }


def candidate(**changes):
    object_id = uuid4()
    value = {
        "candidate_key": "btc-funding-reversal",
        "title": "BTC funding dislocation reversal after crowded positioning",
        "domain_key": "market-microstructure",
        "cluster_key": "funding-reversal",
        "question": "Does elevated BTC funding predict negative future BTC returns over the next four hours?",
        "predictor": "Lagged BTC perpetual funding and trailing return measured on closed bars.",
        "target": "BTCUSDT forward return",
        "horizon": "four hours",
        "causal_timing": "All predictors close before the next-bar decision and the four-hour target window begins.",
        "null_hypothesis": "Conditional forward returns do not differ from zero after realistic execution costs.",
        "predicted_direction": "negative",
        "mechanism": "Crowded leveraged long positioning creates forced selling and costly inventory pressure.",
        "rival_explanations": [
            "Funding reflects trend persistence instead of crowding."
        ],
        "falsification_criteria": [
            "Out-of-sample effect is zero after realistic costs."
        ],
        "features": ["lagged funding rate", "lagged return"],
        "parameter_budget": {
            "maximum_parameters": 3,
            "maximum_variants": 12,
            "parameter_names": ["funding_threshold", "lookback", "holding_period"],
        },
        "data": {
            "venue": "bybit",
            "instrument": "BTCUSDT",
            "timeframe": "1m",
            "required_fields": ["timestamp", "close", "funding_rate", "volume"],
            "minimum_history_observations": 500,
            "liquidity_floor_usd": 0,
        },
        "evidence_object_ids": [object_id],
        "evidence_digests": [DIGEST],
        "equations": [],
        "expected_information_gain": 0.8,
        "feasibility": 0.9,
    }
    value.update(changes)
    return AlphaPredictiveCandidate.model_validate(value), object_id


def test_weekly_mandate_cannot_exceed_seven_days():
    moment = datetime.now(UTC)
    with pytest.raises(ValidationError, match="no longer than seven days"):
        AlphaResearchMandateCreate.model_validate(
            {
                "mandate_key": "week-1",
                "version": "1.0.0",
                "objective": "Run bounded no-capital predictive research on admitted exchange data.",
                "valid_from": moment,
                "valid_until": moment + timedelta(days=8),
                "bulletproof_source_commit": COMMIT,
                "execution_window_start": moment - timedelta(days=30),
                "execution_window_end": moment - timedelta(days=1),
                "dataset_bindings": [binding()],
                "allowed_venues": ["bybit"],
                "allowed_instruments": ["BTCUSDT"],
                "minimum_liquidity_usd": 0,
                "budget": {
                    "maximum_cycles": 2,
                    "maximum_hypotheses": 4,
                    "maximum_total_trials": 8,
                    "maximum_variants_per_hypothesis": 2,
                    "maximum_candidates_per_cycle": 2,
                    "cadence_seconds": 60,
                    "maximum_consecutive_failures": 2,
                },
                "created_by": "founder-operator",
            }
        )


def test_delegated_campaign_requires_mandate_digest():
    with pytest.raises(ValidationError, match="immutable research mandate"):
        AlphaCampaignCreate.model_validate(
            {
                "campaign_key": "alpha004-test",
                "version": "1.0.0",
                "project": "bulletproof-bt",
                "objective": "Run a bounded predictive campaign using admitted real exchange data.",
                "discovery_portfolio_id": uuid4(),
                "dataset_bindings": [binding()],
                "bulletproof_source_commit": COMMIT,
                "allowed_venues": ["bybit"],
                "allowed_instruments": ["BTCUSDT"],
                "budget": {
                    "max_hypotheses": 2,
                    "max_total_trials": 4,
                    "max_variants_per_hypothesis": 2,
                    "max_duration_seconds": 3600,
                    "max_consecutive_failures": 2,
                },
                "created_by": "alpha-continuous-director",
                "execution_protocol": "alpha004-delegated-v1",
                "execution_window_start": datetime.now(UTC) - timedelta(days=30),
                "execution_window_end": datetime.now(UTC) - timedelta(days=1),
            }
        )


def test_candidate_gate_accepts_predictive_available_question_and_rejects_instruction():
    value, object_id = candidate()
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [{"object_id": str(object_id), "content_digest": DIGEST}]
            },
            "datasets": [
                {
                    "binding_index": 0,
                    "venue": "bybit",
                    "instruments": ["BTCUSDT"],
                    "timeframe": "1m",
                    "rows": 10_000,
                    "output_columns": [
                        "timestamp",
                        "close",
                        "funding_rate",
                        "volume",
                    ],
                }
            ],
        }
    )
    mandate = SimpleNamespace(specification={"minimum_liquidity_usd": 0})
    reasons, index = _candidate_reasons(value, cycle, mandate, [])
    assert reasons == []
    assert index == 0

    instruction, _ = candidate(
        question="Run this test and predict future BTC returns over the next four hours?",
        evidence_object_ids=[object_id],
    )
    reasons, _ = _candidate_reasons(instruction, cycle, mandate, [])
    assert "imperative_or_operational_instruction" in reasons


def test_founder_idea_enforces_one_year_and_eight_variant_boundary():
    value, object_id = candidate()
    cycle = SimpleNamespace(
        context={
            "founder_research_idea": {
                "constraints": {"minimum_history_days": 365, "maximum_variants": 8}
            },
            "research_intelligence": {
                "citations": [{"object_id": str(object_id), "content_digest": DIGEST}]
            },
            "datasets": [],
        }
    )
    mandate = SimpleNamespace(
        specification={
            "minimum_liquidity_usd": 0,
            "execution_window_start": "2026-01-01T00:00:00+00:00",
            "execution_window_end": "2026-02-01T00:00:00+00:00",
        }
    )
    reasons, _ = _candidate_reasons(value, cycle, mandate, [])
    assert "founder_variant_budget_exceeded" in reasons
    assert "founder_minimum_history_not_requested" in reasons
    assert "mandate_window_below_founder_minimum" in reasons


def test_llm_equation_is_not_accepted_as_verified_without_receipt():
    value, object_id = candidate()
    raw = value.model_dump(mode="json")
    raw["equations"] = [
        {
            "expression": "r_t = p_t / p_{t-1} - 1",
            "meaning": "The one-period return used as the predictive target.",
            "source_object_id": str(object_id),
            "source_content_digest": DIGEST,
            "source_excerpt": "r_t = p_t / p_{t-1} - 1",
            "verification": "deterministically_verified",
            "verification_receipt_digest": None,
        }
    ]
    with pytest.raises(ValidationError, match="immutable verification receipt"):
        AlphaPredictiveCandidate.model_validate(raw)


def test_source_replayed_equation_cannot_drive_campaign_while_fidelity_is_unqualified():
    base, object_id = candidate()
    raw = base.model_dump(mode="json")
    raw["equations"] = [
        {
            "expression": "r_t = p_t / p_{t-1} - 1",
            "meaning": "The one-period return used as the predictive target.",
            "source_object_id": str(object_id),
            "source_content_digest": DIGEST,
            "source_excerpt": "r_t = p_t / p_{t-1} - 1",
            "verification": "source_replayed",
            "verification_receipt_digest": None,
        }
    ]
    value = AlphaPredictiveCandidate.model_validate(raw)
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [
                    {
                        "object_id": str(object_id),
                        "content_digest": DIGEST,
                        "text": "The source states r_t = p_t / p_{t-1} - 1.",
                    }
                ]
            },
            "datasets": [
                {
                    "binding_index": 0,
                    "venue": "bybit",
                    "instruments": ["BTCUSDT"],
                    "timeframe": "1m",
                    "rows": 10_000,
                    "output_columns": [
                        "timestamp",
                        "close",
                        "funding_rate",
                        "volume",
                    ],
                }
            ],
        }
    )
    mandate = SimpleNamespace(specification={"minimum_liquidity_usd": 0})
    reasons, _ = _candidate_reasons(value, cycle, mandate, [])
    assert "equation_verification_required_for_campaign" in reasons


def test_verified_equation_requires_a_bound_assurance_receipt():
    base, object_id = candidate()
    raw = base.model_dump(mode="json")
    raw["equations"] = [
        {
            "expression": "r_t = p_t / p_{t-1} - 1",
            "meaning": "The one-period return used as the predictive target.",
            "source_object_id": str(object_id),
            "source_content_digest": DIGEST,
            "source_excerpt": "r_t = p_t / p_{t-1} - 1",
            "verification": "deterministically_verified",
            "verification_receipt_digest": "b" * 64,
        }
    ]
    value = AlphaPredictiveCandidate.model_validate(raw)
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [
                    {
                        "object_id": str(object_id),
                        "content_digest": DIGEST,
                        "text": "r_t = p_t / p_{t-1} - 1",
                    }
                ]
            },
            "datasets": [
                {
                    "binding_index": 0,
                    "venue": "bybit",
                    "instruments": ["BTCUSDT"],
                    "timeframe": "1m",
                    "rows": 10_000,
                    "output_columns": ["timestamp", "close", "volume"],
                }
            ],
        }
    )
    mandate = SimpleNamespace(specification={"minimum_liquidity_usd": 0})
    db = MagicMock()
    db.scalar.return_value = None
    reasons, _ = _candidate_reasons(value, cycle, mandate, [], db)
    assert "equation_assurance_receipt_invalid_or_unbound" in reasons
