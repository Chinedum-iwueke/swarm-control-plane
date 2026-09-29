from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_external_worker_is_bounded_and_timer_driven() -> None:
    service = (
        ROOT / "systemd/invariance-swarm-ri017-external-acquisition.service"
    ).read_text()
    timer = (
        ROOT / "systemd/invariance-swarm-ri017-external-acquisition.timer"
    ).read_text()
    assert "NoNewPrivileges=true" in service
    assert "CapabilityBoundingSet=" in service
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in service
    assert "approved_external_sources_v1.json" in service
    assert "OnUnitActiveSec=6h" in timer
    assert "Persistent=true" in timer


def test_installer_pins_commit_and_root_only_credentials() -> None:
    installer = (ROOT / "systemd/install-ri017-external-acquisition.sh").read_text()
    assert 'git -C "$repo" rev-parse HEAD' in installer
    assert "SWARM_ORCHESTRATOR_TOKEN" in installer
    assert "-m 0600" in installer
    assert "systemctl enable --now" in installer

