from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.schemas.alpha_campaign import AlphaCampaignCreate
from app.schemas.alpha_discovery import (
    AlphaPredictiveCandidate,
    AlphaResearchMandateCreate,
)
from app.services.alpha_discovery import _candidate_reasons
from pydantic import ValidationError

DIGEST = "a" * 64
COMMIT = "b" * 40


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
