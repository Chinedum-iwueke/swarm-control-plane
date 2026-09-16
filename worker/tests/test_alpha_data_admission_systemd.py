from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_alpha_data_admission_unit_is_bounded() -> None:
    unit = (
        ROOT / "systemd/invariance-swarm-alpha-data-admission.service"
    ).read_text(encoding="utf-8")

    assert "User=omenka" in unit
    assert "EnvironmentFile=/etc/invariance-swarm/alpha-data-admission.env" in unit
    assert "ReadOnlyPaths=/home/omenka/Projects/bulletproof_bt" in unit
    assert "ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces" in unit
    assert "alpha-data-backups" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "NoNewPrivileges=true" in unit


def test_alpha_data_admission_installer_requires_exact_identity() -> None:
    installer = (
        ROOT / "systemd/install-alpha-data-admission.sh"
    ).read_text(encoding="utf-8")

    assert "vm1-alpha-data-admission" in installer
    assert "root-owned mode 600" in installer
    assert "systemd-analyze verify" in installer
    assert "build_alpha_data_admission_batch.py" in installer
