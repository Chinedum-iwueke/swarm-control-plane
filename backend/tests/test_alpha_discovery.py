from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.schemas.alpha_campaign import AlphaCampaignCreate
from app.schemas.alpha_discovery import (
    AlphaDataAdmissionRecovery,
    AlphaDiscoveryCatalogBinding,
    AlphaDiscoveryStageRetry,
    AlphaFounderResearchIdeaCreate,
    AlphaPredictiveCandidate,
    AlphaResearchMandateCreate,
    AlphaStrategyCapabilityCatalog,
)
from app.services.alpha_discovery import (
    _apply_representation_plans,
    _bounded_context,
    _candidate_enters_novelty_memory,
    _candidate_reasons,
    _discovery_catalog,
    _discovery_corpus,
    _discovery_queries,
    _ensure_data_admission_task,
    _focus_founder_context,
    _missing_admission_fields,
    _normalize_candidate_input,
    _recover_resumed_stage,
    _task,
    reconcile_mandate,
    recover_data_admission,
    recover_discovery_grounding,
    retry_invalid_discovery_stage,
)
from fastapi import HTTPException
from pydantic import ValidationError

DIGEST = "a" * 64
COMMIT = "b" * 40


def test_founder_context_focus_keeps_named_asset_and_strategy_only():
    context = {
        "lake_catalog": {
            "assets": [
                ["perp", "bybit", "BTCUSDT"],
                ["perp", "bybit", "ETHUSDT"],
                ["perp", "binance", "SOLUSDT"],
            ],
            "one_year_coverage_candidates": [
                {"venue": "bybit", "instrument": "BTCUSDT"},
                {"venue": "bybit", "instrument": "ETHUSDT"},
                {"venue": "binance", "instrument": "SOLUSDT"},
            ],
            "receipt_digest": DIGEST,
        },
        "strategy_catalog": {
            "catalog_digest": DIGEST,
            "capabilities": [
                {
                    "hypothesis_id": "L2-H3",
                    "contract_digest": "c" * 64,
                    "research_contract_digest": "d" * 64,
                },
                {
                    "hypothesis_id": "L2-H5",
                    "contract_digest": "e" * 64,
                    "research_contract_digest": "f" * 64,
                },
            ],
        },
        "research_intelligence": {"citations": [{"object_id": "kept"}]},
    }

    focused = _focus_founder_context(
        context,
        "Challenge exact L2-H3 on Bybit ETHUSDT using digest " + "d" * 64,
    )

    assert focused["lake_catalog"]["assets"] == [["perp", "bybit", "ETHUSDT"]]
    assert focused["lake_catalog"]["one_year_coverage_candidates"] == [
        {"venue": "bybit", "instrument": "ETHUSDT"}
    ]
    assert [
        item["hypothesis_id"] for item in focused["strategy_catalog"]["capabilities"]
    ] == ["L2-H3"]
    assert focused["research_intelligence"] == context["research_intelligence"]
    assert focused["founder_context_focus"]["server_side_validation_unchanged"]
    assert len(context["lake_catalog"]["assets"]) == 3
    assert len(context["strategy_catalog"]["capabilities"]) == 2


def test_founder_context_focus_does_not_narrow_open_ended_idea():
    context = {
        "lake_catalog": {"assets": [["perp", "bybit", "BTCUSDT"]]},
        "strategy_catalog": {"capabilities": [{"hypothesis_id": "L2-H3"}]},
    }

    focused = _focus_founder_context(
        context, "Find a novel cross-market predictive relationship."
    )

    assert focused["lake_catalog"]["assets"] == context["lake_catalog"]["assets"]
    assert (
        focused["strategy_catalog"]["capabilities"]
        == context["strategy_catalog"]["capabilities"]
    )


def test_candidate_normalization_is_outcome_blind_and_constraint_only():
    evidence_id = uuid4()
    founder_id = uuid4()
    raw = {
        "question": "Does this point-in-time predictor forecast a future return?",
        "evidence_object_ids": [str(founder_id), str(evidence_id)],
        "evidence_digests": ["b" * 64, DIGEST],
        "data": {"minimum_history_observations": 500_000},
    }
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [
                    {"object_id": str(evidence_id), "content_digest": DIGEST}
                ]
            },
            "founder_research_idea": {
                "constraints": {"minimum_history_days": 365}
            },
        }
    )

    normalized, changes = _normalize_candidate_input(raw, cycle)

    assert normalized["evidence_object_ids"] == [str(evidence_id)]
    assert normalized["evidence_digests"] == [DIGEST]
    assert normalized["data"]["minimum_history_observations"] == 525_600
    assert changes == [
        "discarded_non_replayable_evidence_pairs",
        "raised_history_to_founder_minimum",
    ]
    assert raw["evidence_object_ids"] == [str(founder_id), str(evidence_id)]
    assert raw["data"]["minimum_history_observations"] == 500_000


def test_discovery_catalog_binding_requires_exact_no_authority_receipt():
    receipt_id = uuid4()
    binding = AlphaDiscoveryCatalogBinding(
        producer_receipt_id=receipt_id,
        receipt_digest=DIGEST,
        source_commit=COMMIT,
        allowed_venues=["binance", "bybit"],
        maximum_assets_per_hypothesis=8,
    )
    record = SimpleNamespace(
        milestone="DATA-002",
        producer="bt.institutional.lake_manifest.manifest_catalog_receipt",
        receipt_digest=DIGEST,
        source_commit=COMMIT,
        receipt={
            "authority": {
                "allocation": False,
                "capital": False,
                "orders": False,
                "promotion": False,
            },
            "result": {
                "schema_version": "data002-manifest-catalog-v1.0.0",
                "venue_scope": ["binance", "bybit"],
                "one_year_coverage_candidates": [{}, {}],
                "execution_eligible": False,
            },
        },
    )
    db = MagicMock()
    db.get.return_value = record
    result = _discovery_catalog(db, SimpleNamespace(discovery_catalog=binding))
    assert result["one_year_candidate_count"] == 2
    assert result["execution_authority"] is False
    record.receipt["authority"]["orders"] = True
    with pytest.raises(HTTPException, match="no-authority manifest receipt"):
        _discovery_catalog(db, SimpleNamespace(discovery_catalog=binding))


def test_discovery_context_carries_frozen_execution_constraints(monkeypatch):
    mandate = SimpleNamespace(
        objective="Discover mechanisms.",
        mandate_digest=DIGEST,
        specification={
            "execution_window_start": "2025-05-01T00:00:00Z",
            "execution_window_end": "2026-05-01T00:00:00Z",
            "bulletproof_source_commit": COMMIT,
            "minimum_liquidity_usd": 100_000,
            "strategy_catalog": strategy_catalog(),
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
    assert context["strategy_catalog"] == mandate.specification["strategy_catalog"]
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
        mandate_id=uuid4(),
        expected_mandate_digest=DIGEST,
        idea="Does cross-asset liquidity predict future residual returns?",
        submitted_by="founder-operator",
    )
    assert payload.universe_slices == ["all_eligible"]
    assert payload.universe_selection_policy == "preregistered_point_in_time"
    assert payload.minimum_instruments == 1
    assert payload.maximum_instruments == 8
    legacy = payload.model_copy(update={"universe_slices": ["stable", "volatile"]})
    assert legacy.universe_slices == ["stable", "volatile"]

    with pytest.raises(ValueError, match="minimum instruments"):
        AlphaFounderResearchIdeaCreate(
            mandate_id=uuid4(),
            expected_mandate_digest=DIGEST,
            idea="Does a cross-asset basket predict a future residual return?",
            submitted_by="founder-operator",
            minimum_instruments=3,
            maximum_instruments=2,
        )


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
        representation_task_id=None,
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


def test_failed_data_admission_recovery_reuses_exact_successful_task(monkeypatch):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(
        id=uuid4(),
        status="active",
        valid_from=moment - timedelta(days=1),
        valid_until=moment + timedelta(days=1),
        mandate_digest=DIGEST,
        specification={
            "bulletproof_source_commit": COMMIT,
            "discovery_catalog": {"receipt_digest": "c" * 64},
        },
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        mandate_id=mandate.id,
        status="rejected",
        phase="complete",
        next_action="schedule_next_discovery_cycle",
        completed_at=moment,
    )
    candidate = SimpleNamespace(
        id=uuid4(),
        cycle_id=cycle.id,
        candidate_digest="d" * 64,
        disposition="awaiting_data_admission",
    )
    task = SimpleNamespace(
        id=uuid4(),
        status="succeeded",
        plan_digest="e" * 64,
        input_contract={
            "candidate_id": str(candidate.id),
            "candidate_digest": candidate.candidate_digest,
            "catalog_receipt_digest": "c" * 64,
            "source_commit": COMMIT,
        },
    )
    admission = SimpleNamespace(
        candidate_id=candidate.id,
        task_id=task.id,
        status="failed",
        failure={"error_category": "executor_ValidationError"},
        completed_at=moment,
    )
    founder_idea = SimpleNamespace(status="rejected")
    payload = AlphaDataAdmissionRecovery(
        expected_mandate_digest=DIGEST,
        expected_cycle_id=cycle.id,
        expected_task_id=task.id,
        actor="founder-operator",
        reason="Recover the unchanged successful native receipt batch.",
    )
    db = MagicMock()
    db.get.side_effect = lambda model, identity: {
        cycle.id: cycle,
        candidate.id: candidate,
        task.id: task,
    }.get(identity)
    db.scalar.side_effect = [admission, founder_idea]
    event = MagicMock()
    reconcile = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    monkeypatch.setattr(
        "app.services.alpha_discovery._reconcile_data_admissions", reconcile
    )

    result = recover_data_admission(db, mandate, payload)

    assert result is cycle
    assert cycle.status == "awaiting_data_admission"
    assert cycle.phase == "data_admission"
    assert admission.status == "queued"
    assert admission.failure == {}
    assert founder_idea.status == "processing"
    reconcile.assert_called_once_with(db, mandate, cycle)
    assert event.call_args.args[2] == "selected_panel_admission_recovered"


def test_invalid_representation_retry_supersedes_output_without_rewriting_history(monkeypatch):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(
        id=uuid4(),
        status="active",
        valid_from=moment - timedelta(days=1),
        valid_until=moment + timedelta(days=1),
        mandate_digest=DIGEST,
        budget={"maximum_candidates_per_cycle": 5},
    )
    previous = SimpleNamespace(
        id=uuid4(),
        task_number="A4-example-001-R",
        status="succeeded",
        result={"summary": {"invalid": True}},
        input_contract={
            "mandate_id": str(mandate.id),
            "mandate_digest": DIGEST,
            "cycle_id": "placeholder",
            "stage": "representation",
            "context": {"raw_candidates": [{"candidate_key": "frozen"}]},
        },
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        ordinal=1,
        status="needs_attention",
        phase="representation_selection",
        next_action="review_invalid_representation_output",
        representation_task_id=previous.id,
        completed_at=moment,
        heartbeat_at=moment,
    )
    previous.input_contract["cycle_id"] = str(cycle.id)
    replacement = SimpleNamespace(id=uuid4())
    rejection = SimpleNamespace(
        payload={
            "detail": "rolling window is outside the bounded range",
        }
    )
    db = MagicMock()
    db.scalar.side_effect = [cycle, rejection]
    db.get.return_value = previous
    create_task = MagicMock(return_value=replacement)
    event = MagicMock()
    monkeypatch.setattr("app.services.alpha_discovery._task", create_task)
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    payload = AlphaDiscoveryStageRetry(
        expected_mandate_digest=DIGEST,
        expected_cycle_id=cycle.id,
        actor="codex-loop-recovery",
        reason="Retry the frozen stage after a deployed contract correction.",
    )

    result = retry_invalid_discovery_stage(db, mandate, payload)

    assert result is cycle
    assert cycle.status == "running"
    assert cycle.representation_task_id == replacement.id
    assert previous.status == "succeeded"
    replacement_context = create_task.call_args.args[4]
    assert replacement_context["raw_candidates"] == [{"candidate_key": "frozen"}]
    assert replacement_context["recovery_feedback"] == {
        "previous_task_id": str(previous.id),
        "validation_error": "rolling window is outside the bounded range",
        "correction_requirements": [
            "preserve the frozen hypothesis and metadata-only selection boundary",
            "return a complete plan that validates against the supplied schema",
            "use only declared operations and their bounded parameter contracts",
            "do not inspect outcomes or silently weaken the research question",
        ],
    }
    assert create_task.call_args.kwargs["task_number"].startswith(
        "A4-example-001-R-R"
    )
    assert event.call_args.args[2] == "invalid_discovery_stage_superseded"


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


def test_representation_plan_changes_only_data_shape_and_retains_audit():
    value, _ = candidate()
    raw = value.model_dump(mode="json")
    original_question = raw["question"]
    represented, audit = _apply_representation_plans(
        [raw],
        [
            {
                "schema_version": "adaptive-representation-plan-v1.0.0",
                "candidate_key": raw["candidate_key"],
                "venue": "bybit",
                "instrument": "BTCUSDT",
                "instruments": ["BTCUSDT", "ETHUSDT"],
                "basket_members": [
                    {
                        "instrument": "BTCUSDT",
                        "role": "primary",
                        "legacy_groups": ["stable"],
                        "selection_rationale": "Primary target named by the frozen question.",
                    },
                    {
                        "instrument": "ETHUSDT",
                        "role": "control",
                        "legacy_groups": ["volatile"],
                        "selection_rationale": "Cross-group control isolates broad market movement.",
                    },
                ],
                "source_timeframe": "1m",
                "research_timeframe": "7m",
                "resampling_policy": "right_closed_left_labeled_complete_bars",
                "required_fields": ["ts", "close", "quote_volume"],
                "minimum_history_observations": 525600,
                "liquidity_floor_usd": 1000000,
                "transformations": [
                    {
                        "output_field": "btc_return",
                        "operation": "log_return",
                        "input_fields": ["BTCUSDT__close"],
                        "parameters": {"periods": 1},
                        "fit_policy": "stateless",
                        "rationale": "Scale-safe target return for the causal seven-minute horizon.",
                    },
                    {
                        "output_field": "eth_return",
                        "operation": "log_return",
                        "input_fields": ["ETHUSDT__close"],
                        "parameters": {"periods": 1},
                        "fit_policy": "stateless",
                        "rationale": "Scale-safe control return aligned at the same decision clock.",
                    },
                ],
                "transformation_rationale": (
                    "Seven-minute complete bars align the predictor with its causal horizon."
                ),
                "rejected_alternatives": [
                    "One-minute bars amplify microstructure noise without adding timing evidence."
                ],
                "selection_data_boundary": "metadata_predictors_only_no_targets",
                "outcome_data_consulted": False,
            }
        ],
    )
    assert represented[0]["question"] == original_question
    assert represented[0]["data"]["research_timeframe"] == "7m"
    assert represented[0]["data"]["instruments"] == ["BTCUSDT", "ETHUSDT"]
    assert represented[0]["representation_plan"]["basket_members"][1]["role"] == (
        "control"
    )
    assert audit[raw["candidate_key"]]["outcome_data_consulted"] is False


def test_representation_plan_requires_exact_candidate_coverage():
    value, _ = candidate()
    with pytest.raises(ValueError, match="cover exactly"):
        _apply_representation_plans([value.model_dump(mode="json")], [])


def test_representation_group_claim_must_be_catalog_evidenced():
    value, _ = candidate()
    raw = value.model_dump(mode="json")
    plan = {
        "schema_version": "adaptive-representation-plan-v1.0.0",
        "candidate_key": raw["candidate_key"],
        "venue": "bybit",
        "instrument": "BTCUSDT",
        "instruments": ["BTCUSDT"],
        "basket_members": [{
            "instrument": "BTCUSDT",
            "role": "primary",
            "legacy_groups": ["volatile"],
            "selection_rationale": "The point-in-time label is part of the proposed state.",
        }],
        "source_timeframe": "1m",
        "research_timeframe": "5m",
        "resampling_policy": "left_closed_left_labeled_complete_bars",
        "required_fields": ["ts", "close", "volume"],
        "minimum_history_observations": 525600,
        "liquidity_floor_usd": 1000000,
        "transformations": [{
            "output_field": "btc_return",
            "operation": "log_return",
            "input_fields": ["BTCUSDT__close"],
            "parameters": {"periods": 1},
            "fit_policy": "stateless",
            "rationale": "Returns remove price-level scale from the predictor.",
        }],
        "transformation_rationale": "Five-minute bars match the proposed causal horizon.",
        "rejected_alternatives": ["Raw price levels preserve an avoidable trend."],
        "selection_data_boundary": "metadata_predictors_only_no_targets",
        "outcome_data_consulted": False,
    }
    context = {
        "lake_catalog": {
            "membership_records": [{
                "venue": "bybit",
                "instrument": "BTCUSDT",
                "group": "stable",
                "available": True,
            }]
        }
    }
    with pytest.raises(ValueError, match="not catalog-evidenced"):
        _apply_representation_plans([raw], [plan], context)


def test_representation_plan_rejects_outcome_selection_and_unsafe_fractional_difference():
    value, _ = candidate()
    raw = value.model_dump(mode="json")
    plan = {
        "schema_version": "adaptive-representation-plan-v1.0.0",
        "candidate_key": raw["candidate_key"],
        "venue": "bybit",
        "instrument": "BTCUSDT",
        "instruments": ["BTCUSDT"],
        "basket_members": [
            {
                "instrument": "BTCUSDT",
                "role": "primary",
                "legacy_groups": ["stable"],
                "selection_rationale": "Primary point-in-time target in the frozen question.",
            }
        ],
        "source_timeframe": "1m",
        "research_timeframe": "30m",
        "resampling_policy": "left_closed_left_labeled_complete_bars",
        "required_fields": ["ts", "close", "volume"],
        "minimum_history_observations": 525600,
        "liquidity_floor_usd": 1000000,
        "transformations": [
            {
                "output_field": "stationary_close",
                "operation": "fractional_difference",
                "input_fields": ["BTCUSDT__close"],
                "parameters": {"d": 0.4, "weight_threshold": 0.001},
                "fit_policy": "train_only",
                "rationale": "Reduce persistent price-level behavior while retaining memory.",
            }
        ],
        "transformation_rationale": "Thirty-minute decisions match the stated slower horizon.",
        "rejected_alternatives": ["Log returns remove more low-frequency memory."],
        "selection_data_boundary": "metadata_predictors_only_no_targets",
        "outcome_data_consulted": False,
    }
    represented, _ = _apply_representation_plans([raw], [plan])
    assert represented[0]["representation_plan"]["transformations"][0][
        "parameters"
    ]["d"] == 0.4

    plan["outcome_data_consulted"] = True
    with pytest.raises(ValidationError, match="outcome_data_consulted"):
        _apply_representation_plans([raw], [plan])
    plan["outcome_data_consulted"] = False
    plan["transformations"][0]["parameters"]["d"] = 0.7
    with pytest.raises(ValidationError, match="between 0 and 0.5"):
        _apply_representation_plans([raw], [plan])


def test_representation_task_routes_only_to_dedicated_capability(monkeypatch):
    captured = {}
    built = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        "app.services.alpha_discovery.build_task",
        lambda payload: captured.setdefault("payload", payload) and built,
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery.persist_new_task", lambda *_: None
    )
    mandate = SimpleNamespace(
        id=uuid4(),
        mandate_digest=DIGEST,
        budget={"maximum_candidates_per_cycle": 5},
    )
    cycle = SimpleNamespace(id=uuid4(), ordinal=3)
    assert _task(MagicMock(), mandate, cycle, "representation", {}).id == built.id
    task = captured["payload"]
    assert task.task_number.endswith("-R")
    assert task.required_capabilities == ["data-representation", "market-data-read"]
    assert task.risk_level == 0
    assert task.approval_required is False
    assert task.input_contract["stage"] == "representation"


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


def test_cancelled_campaign_releases_mandate_for_next_cycle(monkeypatch):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(
        id=uuid4(),
        status="active",
        valid_until=moment + timedelta(days=1),
        heartbeat_at=None,
        cycle_count=1,
        hypothesis_count=0,
        trial_count=0,
        budget={
            "maximum_cycles": 10,
            "maximum_hypotheses": 10,
            "maximum_total_trials": 80,
        },
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        campaign_id=uuid4(),
        status="needs_attention",
        phase="campaign",
        next_action="operator_review",
        completed_at=None,
        heartbeat_at=None,
    )
    campaign = SimpleNamespace(
        id=cycle.campaign_id,
        status="cancelled",
        terminal_reason={"category": "operator_cancelled"},
        hypothesis_count=0,
        trial_count=0,
    )
    db = MagicMock()
    db.scalar.return_value = cycle
    db.get.return_value = campaign
    event = MagicMock()
    queued = SimpleNamespace(id=uuid4())
    new_cycle = MagicMock()
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    monkeypatch.setattr(
        "app.services.alpha_discovery._reconcile_data_admissions",
        lambda *_: False,
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery._recover_resumed_stage", lambda *_: False
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery._next_founder_idea", lambda *_: queued
    )
    monkeypatch.setattr("app.services.alpha_discovery._new_cycle", new_cycle)

    reconcile_mandate(db, mandate)

    assert cycle.status == "rejected"
    assert cycle.phase == "complete"
    assert cycle.next_action == "schedule_next_discovery_cycle"
    assert cycle.completed_at is not None
    assert event.call_args.args[2] == "campaign_cancelled_without_candidate"
    new_cycle.assert_called_once_with(db, mandate, queued)


def test_completed_campaign_accounting_is_idempotent(monkeypatch):
    moment = datetime.now(UTC)
    mandate = SimpleNamespace(
        id=uuid4(),
        status="active",
        valid_until=moment + timedelta(days=1),
        heartbeat_at=None,
        cycle_count=1,
        hypothesis_count=1,
        trial_count=8,
        budget={
            "maximum_cycles": 10,
            "maximum_hypotheses": 10,
            "maximum_total_trials": 80,
            "cadence_seconds": 3600,
        },
    )
    cycle = SimpleNamespace(
        id=uuid4(),
        campaign_id=uuid4(),
        status="completed",
        phase="complete",
        next_action="schedule_next_discovery_cycle",
        created_at=moment,
        completed_at=moment,
        heartbeat_at=None,
    )
    campaign = SimpleNamespace(
        id=cycle.campaign_id,
        status="completed_no_candidate",
        hypothesis_count=1,
        trial_count=8,
    )
    db = MagicMock()
    db.scalar.side_effect = [cycle, None]
    db.get.return_value = campaign
    event = MagicMock()
    new_cycle = MagicMock()
    monkeypatch.setattr("app.services.alpha_discovery._event", event)
    monkeypatch.setattr(
        "app.services.alpha_discovery._reconcile_data_admissions",
        lambda *_: False,
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery._recover_resumed_stage", lambda *_: False
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery._next_founder_idea", lambda *_: None
    )
    monkeypatch.setattr("app.services.alpha_discovery._new_cycle", new_cycle)

    reconcile_mandate(db, mandate)

    assert mandate.hypothesis_count == 1
    assert mandate.trial_count == 8
    event.assert_not_called()
    new_cycle.assert_not_called()


def test_mandate_counter_projection_deduplicates_terminal_cycle_evidence():
    from app.services.alpha_discovery import mandate_counter_projection

    first_cycle = uuid4()
    second_cycle = uuid4()
    events = [
        SimpleNamespace(event_type="cycle_started", cycle_id=first_cycle, payload={}),
        SimpleNamespace(
            event_type="campaign_completed_without_candidate",
            cycle_id=first_cycle,
            payload={"hypotheses": 1, "trials": 8},
        ),
        SimpleNamespace(
            event_type="campaign_completed_without_candidate",
            cycle_id=first_cycle,
            payload={"hypotheses": 1, "trials": 8},
        ),
        SimpleNamespace(event_type="cycle_started", cycle_id=second_cycle, payload={}),
        SimpleNamespace(
            event_type="campaign_completed_without_candidate",
            cycle_id=second_cycle,
            payload={"hypotheses": 2, "trials": 4},
        ),
    ]

    assert mandate_counter_projection(events) == {
        "cycle_count": 2,
        "hypothesis_count": 3,
        "trial_count": 12,
        "completed_cycle_ids": sorted([str(first_cycle), str(second_cycle)]),
        "duplicate_completion_events": 1,
    }


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


def strategy_catalog():
    core = {
        "schema_version": "alpha-strategy-capability-catalog-v1.0.0",
        "source_commit": COMMIT,
        "capabilities": [
            {
                "hypothesis_id": "ALPHA-WEEKEND-MOMENTUM",
                "title": "Weekend lagged-return momentum",
                "description": "Tests whether lagged weekend returns predict future returns.",
                "hypothesis_family": "lagged-return-momentum",
                "strategy": "lagged_return_momentum",
                "input_mode": "single_instrument",
                "maximum_instruments": 1,
                "signal_timeframes": ["1m"],
                "variant_count": 2,
                "logging_requirements": ["decision_trace", "stop_price"],
                "reuse_blockers": [],
                "bounded_weekly_reuse_eligible": True,
                "contract_path": "research/hypotheses/alpha_weekend_momentum.yaml",
                "contract_digest": "c" * 64,
            }
        ],
        "capital_or_order_authority": False,
        "claim_boundary": (
            "Catalog membership proves native implementation only, not predictive value."
        ),
    }
    from app.services.graph import digest_document

    return {**core, "catalog_digest": digest_document(core)}


def test_strategy_catalog_v11_requires_semantic_contracts():
    document = strategy_catalog()
    document["schema_version"] = "alpha-strategy-capability-catalog-v1.1.0"
    from app.services.graph import digest_document

    core = {key: value for key, value in document.items() if key != "catalog_digest"}
    document["catalog_digest"] = digest_document(core)
    with pytest.raises(ValidationError, match="immutable research semantics"):
        AlphaStrategyCapabilityCatalog.model_validate(document)

    capability = document["capabilities"][0]
    capability["research_contract"] = {
        "parameter_grid": {"lookback": [30, 60]},
        "entry": {"order_timing": "next_bar"},
        "truth_contract": {"no_lookahead": True},
    }
    capability["research_contract_digest"] = "d" * 64
    core = {key: value for key, value in document.items() if key != "catalog_digest"}
    document["catalog_digest"] = digest_document(core)

    result = AlphaStrategyCapabilityCatalog.model_validate(document)
    assert result.capabilities[0].research_contract["parameter_grid"] == {
        "lookback": [30, 60]
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
                "strategy_catalog": strategy_catalog(),
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


def test_manifest_visible_basket_waits_for_content_admission():
    value, object_id = candidate()
    value.data.instruments = ["BTCUSDT", "ETHUSDT"]
    value.data.research_timeframe = "7m"
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [{"object_id": str(object_id), "content_digest": DIGEST}]
            },
            "datasets": [],
            "lake_catalog": {
                "discovery_authority": True,
                "one_year_coverage_candidates": [
                    {
                        "venue": "bybit",
                        "instrument": instrument,
                        "timeframe": "1m",
                        "fetch_status": "success",
                        "missing_rows": 0,
                    }
                    for instrument in ("BTCUSDT", "ETHUSDT")
                ],
            },
        }
    )
    mandate = SimpleNamespace(
        specification={
            "minimum_liquidity_usd": 0,
            "discovery_catalog": {"maximum_assets_per_hypothesis": 8},
        }
    )
    reasons, binding_index = _candidate_reasons(value, cycle, mandate, [])
    assert reasons == ["data_admission_required"]
    assert binding_index is None
    assert value.data.resampling_policy == "left_closed_left_labeled_complete_bars"


def test_primary_only_admission_cannot_satisfy_a_declared_basket():
    value, object_id = candidate()
    value.data.instruments = ["BTCUSDT", "ETHUSDT"]
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
                    "rows": 1_000_000,
                    "output_columns": ["timestamp", "close", "volume"],
                }
            ],
            "lake_catalog": {"discovery_authority": False},
        }
    )
    mandate = SimpleNamespace(specification={"minimum_liquidity_usd": 0})

    reasons, binding_index = _candidate_reasons(value, cycle, mandate, [])

    assert "data002_003_availability_not_demonstrated" in reasons
    assert binding_index is None


def test_single_panel_native_strategy_cannot_silently_consume_a_basket():
    value, object_id = candidate(reusable_hypothesis_id="ALPHA-WEEKEND-MOMENTUM")
    value.data.instruments = ["BTCUSDT", "ETHUSDT"]
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [{"object_id": str(object_id), "content_digest": DIGEST}]
            },
            "datasets": [
                {
                    "binding_index": 0,
                    "venue": "bybit",
                    "instruments": ["BTCUSDT", "ETHUSDT"],
                    "timeframe": "1m",
                    "rows": 1_000_000,
                    "output_columns": ["timestamp", "close", "funding_rate", "volume"],
                }
            ],
        }
    )
    mandate = SimpleNamespace(
        specification={
            "minimum_liquidity_usd": 0,
            "strategy_catalog": strategy_catalog(),
        }
    )
    reasons, _ = _candidate_reasons(value, cycle, mandate, [])
    assert "reusable_hypothesis_input_cardinality_mismatch" in reasons


def test_manifest_visibility_without_mandate_binding_cannot_expand_scope():
    value, object_id = candidate()
    value.data.instrument = "ETHUSDT"
    value.data.instruments = ["ETHUSDT"]
    cycle = SimpleNamespace(
        context={
            "research_intelligence": {
                "citations": [{"object_id": str(object_id), "content_digest": DIGEST}]
            },
            "datasets": [],
            "lake_catalog": {
                "discovery_authority": False,
                "one_year_coverage_candidates": [
                    {
                        "venue": "bybit",
                        "instrument": "ETHUSDT",
                        "timeframe": "1m",
                        "fetch_status": "success",
                        "missing_rows": 0,
                    }
                ],
            },
        }
    )
    mandate = SimpleNamespace(specification={"minimum_liquidity_usd": 0})
    reasons, _ = _candidate_reasons(value, cycle, mandate, [])
    assert "data002_003_availability_not_demonstrated" in reasons
    assert "data_admission_required" not in reasons


def test_manifest_visible_basket_creates_bounded_no_approval_admission_task(
    monkeypatch,
):
    task_id = uuid4()
    task = SimpleNamespace(id=task_id)
    captured = {}
    monkeypatch.setattr(
        "app.services.alpha_discovery.build_task",
        lambda payload: captured.setdefault("payload", payload) and task,
    )
    monkeypatch.setattr(
        "app.services.alpha_discovery.persist_new_task",
        lambda _db, value: captured.setdefault("task", value),
    )
    candidate_record = SimpleNamespace(
        id=uuid4(),
        candidate_digest="c" * 64,
        document={
            "data": {
                "venue": "bybit",
                "instrument": "BTCUSDT",
                "instruments": ["BTCUSDT", "ETHUSDT"],
                "timeframe": "1m",
                "research_timeframe": "7m",
                "required_fields": [
                    "ts",
                    "BTCUSDT__close",
                    "ETHUSDT__close",
                ],
            }
        },
    )
    catalog_id = uuid4()
    mandate = SimpleNamespace(
        mandate_digest=DIGEST,
        specification={
            "bulletproof_source_commit": COMMIT,
            "discovery_catalog": {
                "producer_receipt_id": str(catalog_id),
                "receipt_digest": "d" * 64,
            },
        },
    )
    db = MagicMock()
    db.scalar.return_value = None
    admission = _ensure_data_admission_task(db, mandate, candidate_record)
    contract = captured["payload"].input_contract
    assert contract["assets"] == [
        {
            "venue": "bybit",
            "instrument": "BTCUSDT",
            "timeframe": "1m",
            "required_fields": ["close", "ts"],
        },
        {
            "venue": "bybit",
            "instrument": "ETHUSDT",
            "timeframe": "1m",
            "required_fields": ["close", "ts"],
        },
    ]
    assert captured["payload"].approval_required is False
    assert captured["payload"].risk_level == 0
    assert contract["authority"] == "no_capital_data_admission"
    assert admission.task_id == task_id


def test_selected_panel_admission_fails_closed_on_missing_candidate_fields():
    assets = [
        {
            "venue": "bybit",
            "instrument": "ETHUSDT",
            "timeframe": "1m",
            "required_fields": ["ts", "close", "quote_volume"],
        }
    ]
    receipts = [
        {
            "result": {
                "venue": "bybit",
                "instrument": "ETHUSDT",
                "timeframe": "1m",
                "output_columns": ["ts", "open", "high", "low", "close", "volume"],
            }
        }
    ]

    assert _missing_admission_fields(receipts, assets) == (
        assets[0],
        ["quote_volume"],
    )


def test_founder_idea_enforces_one_year_and_eight_variant_boundary():
    value, object_id = candidate()
    cycle = SimpleNamespace(
        context={
            "founder_research_idea": {
                "constraints": {
                    "minimum_history_days": 365,
                    "maximum_variants": 8,
                    "minimum_instruments": 2,
                    "maximum_instruments": 4,
                }
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
    assert "founder_minimum_instruments_not_met" in reasons
    assert "mandate_window_below_founder_minimum" in reasons


def test_schema_invalid_candidate_does_not_enter_novelty_memory():
    invalid = SimpleNamespace(
        disposition="rejected", reason_codes=["candidate_schema_invalid"]
    )
    scientific_rejection = SimpleNamespace(
        disposition="rejected", reason_codes=["semantic_duplicate_prior_question"]
    )
    accepted = SimpleNamespace(disposition="accepted", reason_codes=[])

    assert _candidate_enters_novelty_memory(invalid) is False
    assert _candidate_enters_novelty_memory(scientific_rejection) is True
    assert _candidate_enters_novelty_memory(accepted) is True


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
