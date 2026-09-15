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
        if "quantitative-receipts" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "source_commit": ("b" if request.url.path.endswith(fresh) else "a")
                    * 40
                },
            )
        assert request.method == "POST"
        payload = json.loads(request.content)
        assert payload["dataset_bindings"][0]["producer_receipt_id"] == fresh
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
    arguments = [str(script), "--bulletproof-source-commit", "b" * 40]
    if fresh_receipt:
        arguments.extend(["--producer-receipt-id", fresh])
    monkeypatch.setattr(sys, "argv", arguments)
    if fresh_receipt:
        assert module.main() == 0
        assert len(posted) == 1
    else:
        with pytest.raises(RuntimeError, match="no mandate was written"):
            module.main()
        assert posted == []
