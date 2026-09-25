import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest


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
                            "dataset_bindings": [{"producer_receipt_id": old}],
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
        assert payload["dataset_bindings"][0]["producer_receipt_digest"] == "8" * 64
        assert payload["dataset_bindings"][0]["dataset_digest"] == "9" * 64
        assert payload["dataset_bindings"][0]["rows"] == 525_600
        assert "quote_volume" in payload["dataset_bindings"][0]["output_columns"]
        assert payload["discovery_catalog"] == {
            "producer_receipt_id": catalog_id,
            "receipt_digest": "c" * 64,
            "source_commit": "d" * 40,
            "allowed_venues": ["binance", "bybit"],
            "selection_policy": "point_in_time_pre_outcome",
            "maximum_assets_per_hypothesis": 8,
        }
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
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=json.dumps(strategy_catalog), stderr=""
        ),
    )
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
