import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest


def test_compatible_campaign_bindings_unions_and_deduplicates_same_commit():
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    spec = importlib.util.spec_from_file_location("mandate_binding_union", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = {
        "dataset_build_id": "11111111-1111-4111-8111-111111111111",
        "catalog_id": "22222222-2222-4222-8222-222222222222",
        "lake_governance_snapshot_id": "33333333-3333-4333-8333-333333333333",
        "producer_receipt_id": "44444444-4444-4444-8444-444444444444",
        "dataset_key": "bybit-btcusdt-perp-1m",
        "partition_digests": ["1" * 64],
        "evidence_class": "live_exchange_history",
        "research_principal": "alpha-research-runner",
    }
    second = {
        **first,
        "dataset_build_id": "55555555-5555-4555-8555-555555555555",
        "producer_receipt_id": "66666666-6666-4666-8666-666666666666",
        "dataset_key": "binance-ethusdt-perp-1m",
        "partition_digests": ["2" * 64],
    }
    campaigns = [
        {
            "id": "first",
            "specification": {
                "bulletproof_source_commit": "a" * 40,
                "dataset_bindings": [first],
            },
        },
        {
            "id": "second",
            "specification": {
                "bulletproof_source_commit": "a" * 40,
                "dataset_bindings": [first, second],
            },
        },
        {
            "id": "other-commit",
            "specification": {
                "bulletproof_source_commit": "b" * 40,
                "dataset_bindings": [second],
            },
        },
    ]

    result = module.compatible_campaign_bindings(
        campaigns, source_commit="a" * 40
    )

    assert len(result) == 2
    assert {item["dataset_key"] for item in result} == {
        "bybit-btcusdt-perp-1m",
        "binance-ethusdt-perp-1m",
    }
    assert module.compatible_campaign_bindings(
        campaigns, source_commit="a" * 40, source_campaign_id="first"
    ) == [first]


def test_explicit_admission_selects_matching_partition_from_basket() -> None:
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    spec = importlib.util.spec_from_file_location("mandate_explicit_binding", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt_id = module.UUID("77777777-7777-4777-8777-777777777777")
    bindings = [
        {
            "dataset_build_id": f"{index}" * 8 + "-1111-4111-8111-111111111111",
            "catalog_id": "22222222-2222-4222-8222-222222222222",
            "lake_governance_snapshot_id": "33333333-3333-4333-8333-333333333333",
            "producer_receipt_id": "44444444-4444-4444-8444-444444444444",
            "dataset_key": f"panel-{index}",
            "partition_digests": [str(index) * 64],
            "evidence_class": "live_exchange_history",
            "research_principal": "alpha-research-runner",
        }
        for index in (1, 2)
    ]

    result = module.binding_for_explicit_admission(
        {"dataset_bindings": bindings},
        {"dataset_digest": "2" * 64},
        receipt_id,
    )

    assert len(result) == 1
    assert result[0]["dataset_key"] == "panel-2"
    assert result[0]["producer_receipt_id"] == str(receipt_id)


@pytest.mark.parametrize(
    "arguments,message",
    [
        (["--window-start", "2025-05-01T00:00:00Z"], "Supply both"),
        (
            [
                "--window-start",
                "2026-04-01T00:00:00Z",
                "--window-end",
                "2026-05-01T00:00:00Z",
            ],
            "365 days",
        ),
        (
            ["--window-start", "2025-05-01", "--window-end", "2026-05-01"],
            "require a timezone",
        ),
        (["--bulletproof-source-commit", "main"], "40-character reviewed commit"),
    ],
)
def test_mandate_override_validation_precedes_network_or_credentials(
    arguments, message
):
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    result = subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
        env={},
        check=False,
    )
    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.parametrize("fresh_receipt", [False, True])
def test_engine_override_requires_matching_native_admission(monkeypatch, fresh_receipt):
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    spec = importlib.util.spec_from_file_location("mandate_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = "11111111-1111-4111-8111-111111111111"
    fresh = "22222222-2222-4222-8222-222222222222"
    posted = []
    catalog_id = "33333333-3333-4333-8333-333333333333"

    def handler(request):
        if request.url.path.endswith("alpha-campaigns"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "source",
                        "specification": {
                            "dataset_bindings": [
                                {
                                    "dataset_build_id": "44444444-4444-4444-8444-444444444444",
                                    "catalog_id": "55555555-5555-4555-8555-555555555555",
                                    "lake_governance_snapshot_id": "66666666-6666-4666-8666-666666666666",
                                    "producer_receipt_id": old,
                                    "dataset_key": "bybit-btcusdt-perp-1m",
                                    "partition_digests": ["9" * 64],
                                    "evidence_class": "live_exchange_history",
                                    "research_principal": "alpha-research-runner",
                                }
                            ],
                            "bulletproof_source_commit": "a" * 40,
                            "execution_window_start": "2025-05-01T00:00:00Z",
                            "execution_window_end": "2026-05-01T00:00:00Z",
                            "allowed_venues": ["bybit"],
                            "allowed_instruments": ["BTCUSDT"],
                        },
                    }
                ],
            )
        if request.url.path.endswith("lake-inventory"):
            return httpx.Response(
                200,
                json={
                    "status": "manifest_catalog_visible_unadmitted",
                    "receipt_id": catalog_id,
                    "receipt_digest": "c" * 64,
                    "source_commit": "d" * 40,
                    "venue_scope": ["binance", "bybit"],
                    "one_year_coverage_candidates": [
                        {
                            "venue": "bybit",
                            "instrument": "BTCUSDT",
                            "timeframe": "1m",
                            "fetch_status": "success",
                            "missing_rows": 0,
                            "first_ts": "2025-09-30T00:00:00Z",
                            "last_ts": "2026-09-29T23:59:00Z",
                        },
                        {
                            "venue": "binance",
                            "instrument": "ETHUSDT",
                            "timeframe": "1m",
                            "fetch_status": "success",
                            "missing_rows": 0,
                            "first_ts": "2025-09-30T00:00:00Z",
                            "last_ts": "2026-09-29T23:59:00Z",
                        }
                    ],
                    "execution_authority": False,
                },
            )
        if "quantitative-receipts" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "id": fresh if request.url.path.endswith(fresh) else old,
                    "source_commit": ("b" if request.url.path.endswith(fresh) else "a")
                    * 40,
                    "dataset_digest": "9" * 64,
                    "receipt_digest": "8" * 64,
                    "receipt": {
                        "result": {
                            "venue": "bybit",
                            "instrument": "BTCUSDT",
                            "row_count": 525_600,
                            "output_columns": [
                                "ts",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "quote_volume",
                            ],
                            "evidence_class": "live_exchange_history",
                        }
                    },
                },
            )
        assert request.method == "POST"
        payload = json.loads(request.content)
        assert payload["dataset_bindings"][0]["producer_receipt_id"] == fresh
        assert set(payload["dataset_bindings"][0]) == module.BINDING_KEYS
        assert payload["discovery_catalog"] == {
            "producer_receipt_id": catalog_id,
            "receipt_digest": "c" * 64,
            "source_commit": "d" * 40,
            "allowed_venues": ["binance", "bybit"],
            "selection_policy": "point_in_time_pre_outcome",
            "maximum_assets_per_hypothesis": 100,
            "large_basket_threshold": 20,
            "large_basket_policy": (
                "point_in_time_overlap_liquidity_and_compute_admission"
            ),
        }
        assert payload["historical_window_policy"] == {
            "primary_policy": "latest_complete_utc_year",
            "primary_duration_days": 365,
            "deep_validation_max_days": 1095,
            "deep_validation_requires": [
                "primary_window_survivor",
                "independent_review_complete",
                "explicit_followup_contract",
            ],
        }
        start = module.datetime.fromisoformat(payload["execution_window_start"])
        end = module.datetime.fromisoformat(payload["execution_window_end"])
        assert end - start == module.timedelta(days=365)
        assert end.isoformat() == "2026-09-30T00:00:00+00:00"
        assert payload["budget"]["question_queue_low_watermark"] == 12
        assert payload["budget"]["maximum_parallel_campaigns"] == 3
        assert payload["allowed_venues"] == ["binance", "bybit"]
        assert payload["allowed_instruments"] == ["BTCUSDT", "ETHUSDT"]
        posted.append(payload)
        return httpx.Response(201, json={"status": "awaiting_approval"})

    real_client = httpx.Client
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setenv("SWARM_API_URL", "https://test.invalid")
    monkeypatch.setenv("SWARM_ORCHESTRATOR_TOKEN", "test-not-a-real-token")
    strategy_catalog = {
        "schema_version": "alpha-strategy-capability-catalog-v1.0.0",
        "source_commit": "b" * 40,
        "capabilities": [
            {
                "hypothesis_id": "ALPHA-WEEKEND-MOMENTUM",
                "title": "Weekend lagged-return momentum",
                "description": "Tests whether lagged returns predict future returns.",
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
                "contract_digest": "e" * 64,
            }
        ],
        "capital_or_order_authority": False,
        "claim_boundary": "Native implementation inventory only; no alpha is inferred.",
        "catalog_digest": "f" * 64,
    }
    def run(command, **kwargs):
        stdout = (
            "b" * 40 + "\n"
            if command[:3] == ["git", "-C", "/home/omenka/Projects/bulletproof_bt"]
            else json.dumps(strategy_catalog)
        )
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout=stdout, stderr=""
        )

    monkeypatch.setattr(module.subprocess, "run", run)
    arguments = [str(script), "--bulletproof-source-commit", "b" * 40]
    if fresh_receipt:
        arguments.extend(["--producer-receipt-id", fresh])
    monkeypatch.setattr(sys, "argv", arguments)
    if fresh_receipt:
        assert module.main() == 0
        assert len(posted) == 1
        assert posted[0]["strategy_catalog"] == strategy_catalog
    else:
        with pytest.raises(RuntimeError, match="no mandate was written"):
            module.main()
        assert posted == []


def test_recent_catalog_window_uses_latest_complete_bar_not_wall_clock():
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    spec = importlib.util.spec_from_file_location("mandate_window", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = {
        "one_year_coverage_candidates": [
            {
                "venue": "bybit",
                "timeframe": "1m",
                "fetch_status": "success",
                "missing_rows": 0,
                "last_ts": 1_798_675_140_000,
            },
            {
                "venue": "binance",
                "timeframe": "1m",
                "fetch_status": "success",
                "missing_rows": 1,
                "last_ts": "2099-01-01T00:00:00Z",
            },
        ]
    }

    start, end = module.recent_catalog_window(catalog, venues={"binance", "bybit"})

    assert end - start == module.timedelta(days=365)
    assert end.second == 0
    assert end.microsecond == 0
