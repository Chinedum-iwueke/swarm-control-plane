from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_derived_state_orchestrator_is_bounded_and_restartable() -> None:
    unit = (
        ROOT / "worker/systemd/invariance-swarm-derived-state-orchestrator.service"
    ).read_text(encoding="utf-8")

    assert "WorkingDirectory=/srv/invariance/swarm/control-plane-runtime" in unit
    assert "python -m app.workers.derived_state --continuous" in unit
    assert "--no-deps api" in unit
    assert "Restart=on-failure" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "EnvironmentFile" not in unit


def test_derived_state_orchestrator_installer_targets_systemd() -> None:
    installer = (
        ROOT / "worker/systemd/install-derived-state-orchestrator.sh"
    ).read_text(encoding="utf-8")

    assert "/etc/systemd/system" in installer
    assert "daemon-reload" in installer
    assert "from app.services.derived_state import derived_state_status" in installer
    assert "deployed API image does not contain RI-016" in installer
    assert "--enable" in installer
    assert "--start" in installer
