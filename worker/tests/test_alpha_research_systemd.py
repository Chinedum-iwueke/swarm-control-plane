from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_alpha_executor_unit_is_hardened_and_separate() -> None:
    unit = (
        ROOT / "systemd/invariance-swarm-alpha-research-executor.service"
    ).read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/invariance-swarm/alpha002-executor.env" in unit
    assert "User=omenka" in unit
    assert "NoNewPrivileges=true" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "ReadOnlyPaths=/home/omenka/Projects/bulletproof_bt" in unit
    assert "ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces" in unit
