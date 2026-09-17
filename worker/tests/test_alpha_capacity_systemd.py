import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_capacity_executor_supports_codex_inside_bounded_sandbox() -> None:
    unit = (
        ROOT / "systemd/invariance-swarm-alpha-capacity-executor@.service"
    ).read_text(encoding="utf-8")

    for setting in (
        "User=omenka",
        "ProtectSystem=strict",
        "ProtectHome=read-only",
        "NoNewPrivileges=true",
        "CapabilityBoundingSet=",
        "Environment=NODE_OPTIONS=--jitless",
        "ReadOnlyPaths=/home/omenka/Projects/bulletproof_bt",
        "ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces",
    ):
        assert setting in unit
    assert "MemoryDenyWriteExecute=true" not in unit
    assert "Codex's isolated Node host" in unit


def test_capacity_installer_remains_explicit_and_valid_shell() -> None:
    installer = ROOT / "systemd/install-alpha-capacity.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    script = installer.read_text(encoding="utf-8")

    assert "test \"$(id -u)\" -eq 0" in script
    assert "systemctl daemon-reload" in script
    assert "systemctl enable --now" in script
