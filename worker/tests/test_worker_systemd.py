from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_coding_worker_runs_codex_without_weakening_wx_protection() -> None:
    unit = (ROOT / "systemd/invariance-swarm-worker.service").read_text(
        encoding="utf-8"
    )

    assert "Environment=NODE_OPTIONS=--jitless" in unit
    assert "MemoryDenyWriteExecute=true" in unit
