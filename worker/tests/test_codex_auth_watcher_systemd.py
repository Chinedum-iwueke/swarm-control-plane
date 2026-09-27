import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_watcher_unit_uses_shared_writable_runtime_and_systemd_credential() -> None:
    unit = (
        ROOT / "systemd/invariance-swarm-codex-auth-watcher.service"
    ).read_text(encoding="utf-8")
    assert "User=omenka" in unit
    assert "LoadCredential=orchestrator_token:" in unit
    assert "NoNewPrivileges=true" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "ReadWritePaths=/var/lib/invariance-swarm/codex-discovery-runtime" in unit
    assert "SWARM_ORCHESTRATOR_TOKEN" not in unit


def test_watcher_installer_is_valid_shell_and_restricts_token() -> None:
    installer = ROOT / "systemd/install-codex-auth-watcher.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    value = installer.read_text(encoding="utf-8")
    assert "-m 0600" in value
    assert "systemctl enable --now" in value
