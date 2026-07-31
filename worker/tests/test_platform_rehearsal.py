import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "rehearse_platform_runbook.py"


def _module():
    spec = importlib.util.spec_from_file_location("platform_rehearsal", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_commit_allows_root_owned_checkout_boundary(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Completed:
        stdout = "a" * 40 + "\n"

    def run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Completed()

    module = _module()
    monkeypatch.setattr(module.subprocess, "run", run)
    source = Path("/srv/invariance/swarm/repositories/swarm-control-plane")

    assert module._source_commit(source) == "a" * 40
    assert captured["args"] == [
        "git",
        "-c",
        f"safe.directory={source}",
        "-C",
        str(source),
        "rev-parse",
        "HEAD",
    ]
    assert captured["kwargs"] == {
        "check": True,
        "capture_output": True,
        "text": True,
        "timeout": 30,
    }
