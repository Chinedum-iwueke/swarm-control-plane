from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_replenisher_is_unprivileged_bounded_and_separate_from_lake_checkout():
    unit = (ROOT / "systemd/invariance-swarm-disc010-replenisher.service").read_text()

    assert "User=omenka" in unit
    assert "Type=oneshot" in unit
    assert "--target-active 3 --max-workers 6" in unit
    assert "--data-root /home/omenka/Projects/bulletproof_bt/research_data" in unit
    assert "WorkingDirectory=/home/omenka/Projects/bulletproof_bt-production" in unit
    assert "EnvironmentFile=/etc/invariance-swarm/disc010-replenisher.env" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "RestrictAddressFamilies=AF_UNIX" in unit


def test_replenisher_timer_is_persistent_and_bounded():
    timer = (ROOT / "systemd/invariance-swarm-disc010-replenisher.timer").read_text()

    assert "OnUnitInactiveSec=15s" in timer
    assert "AccuracySec=1s" in timer
    assert "RandomizedDelaySec=2s" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer


def test_publisher_is_network_bounded_and_canonical():
    unit = (ROOT / "systemd/invariance-swarm-disc010-publisher.service").read_text()
    timer = (ROOT / "systemd/invariance-swarm-disc010-publisher.timer").read_text()

    assert "worker/scripts/disc010_publish.py" in unit
    assert "disc010-orchestrator.token" in unit
    assert "NoNewPrivileges=true" in unit
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in unit
    assert "OnUnitActiveSec=2min" in timer
    assert "Persistent=true" in timer


def test_installer_requires_exact_deployed_source_and_root_owned_environment():
    installer = (ROOT / "systemd/install-disc010-replenisher.sh").read_text()

    assert 'test "$(id -u)" -eq 0' in installer
    assert 'git -C "$native" rev-parse HEAD' in installer
    assert 'git -C "$control" rev-parse HEAD' in installer
    assert "/etc/invariance-swarm/disc010-replenisher.env" in installer
    assert "-o root -g root -m 0600" in installer
    assert "invariance-swarm-disc010-replenisher.timer" in installer
    assert "invariance-swarm-disc010-publisher.timer" in installer
    assert "/etc/invariance-swarm/disc010-orchestrator.token" in installer
    assert "alpha-capacity-state.json" in installer
    assert "(.jobs | length) == 0" in installer
    assert "systemctl restart invariance-swarm-alpha-capacity-director.service" in installer
    assert installer.index("(.jobs | length) == 0") < installer.index(
        "systemctl restart invariance-swarm-alpha-capacity-director.service"
    )
