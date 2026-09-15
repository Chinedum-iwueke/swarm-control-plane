import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def supervisor():
    path = Path(__file__).parents[1] / "scripts/alpha007_inventory_supervisor.py"
    spec = importlib.util.spec_from_file_location("inventory_supervisor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operator_bridge_uses_async_existing_client(supervisor):
    code = supervisor.REMOTE.split("python\" -c '", 1)[1].rsplit("'", 1)[0]
    ast.parse(code)
    assert "hermes_mission_control.control_plane" in code
    assert 'await client._request("POST"' in code
    assert "await client.close()" in code
    assert "asyncio.run(send())" in code


def test_publish_keeps_credentials_remote(supervisor, monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured.update(command=command, **kwargs)
        return SimpleNamespace(stdout='{"id":"receipt-id"}')

    monkeypatch.setattr(supervisor.subprocess, "run", run)
    result = supervisor.publish("mac2", "/v1/operations/lake-inventory/report", {"state": "running"})
    assert result == {"id": "receipt-id"}
    assert captured["command"][:3] == ["ssh", "-o", "BatchMode=yes"]
    assert json.loads(captured["input"])["payload"] == {"state": "running"}
    assert "token" not in captured["input"].lower()
    assert captured["timeout"] == 90


def test_failed_ledger_prevents_scan(supervisor, monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["supervisor", "--native-repo", str(tmp_path),
                        "--data-root", str(tmp_path), "--python", "/bin/false",
                        "--output-dir", str(tmp_path / "state")])
    monkeypatch.setattr(supervisor.subprocess, "check_output",
                        lambda command, **kwargs: "" if "status" in command else "a" * 40)
    monkeypatch.setattr(supervisor, "publish", lambda *args: (_ for _ in ()).throw(RuntimeError("ledger unavailable")))
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("scan launched"))
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        supervisor.main()
