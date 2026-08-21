from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "systemd/invariance-swarm-research-worker.service"
INSTALLER = ROOT / "systemd/install-research-worker.sh"


def test_research_worker_has_dedicated_identity_and_continuous_command() -> None:
    unit = UNIT.read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/invariance-swarm/vm1-research-worker.env" in unit
    assert "invariance-swarm-worker run" in unit
    assert "User=omenka" in unit
    assert "NoNewPrivileges=true" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "ReadOnlyPaths=/home/omenka/Projects/bulletproof_bt" in unit


def test_research_worker_installer_requires_explicit_activation() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "enable_service=false" in installer
    assert "start_service=false" in installer
    assert "--enable" in installer
    assert "--start" in installer
    assert "vm1-research-worker.env" in installer
