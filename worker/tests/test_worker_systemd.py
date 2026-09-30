from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_coding_worker_runs_codex_without_weakening_wx_protection() -> None:
    unit = (ROOT / "systemd/invariance-swarm-worker.service").read_text(
        encoding="utf-8"
    )

    assert "Environment=NODE_OPTIONS=--jitless" in unit
    assert "MemoryDenyWriteExecute=true" in unit

    replica = (ROOT / "systemd/invariance-swarm-worker@.service").read_text(
        encoding="utf-8"
    )
    assert "engineering worker replica %i" in replica
    assert "EnvironmentFile=/etc/invariance-swarm/vm1-worker.env" in replica
    assert "MemoryDenyWriteExecute=true" in replica

    installer = (ROOT / "systemd/install.sh").read_text(encoding="utf-8")
    assert "SWARM_ENGINEERING_REPLICAS:-5" in installer
    assert "invariance-swarm-worker@${slot}.service" in installer
