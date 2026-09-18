import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_reviewer_service_is_isolated_bounded_and_read_only():
    unit = (ROOT / "systemd/invariance-swarm-alpha-reviewer@.service").read_text()
    for setting in (
        "User=omenka", "ProtectSystem=strict", "ProtectHome=read-only",
        "NoNewPrivileges=true", "CapabilityBoundingSet=", "MemoryMax=2G",
        "MemoryHigh=1G", "CPUQuota=100%", "OOMPolicy=stop", "TasksMax=128",
        "KillMode=control-group", "EnvironmentFile=/etc/invariance-swarm/alpha-%i-reviewer.env",
        "Environment=SWARM_CODEX_HOME=/var/lib/invariance-swarm/codex-%i-reviewer-runtime",
        "ReadWritePaths=/var/lib/invariance-swarm/codex-%i-reviewer-runtime",
        "BindReadOnlyPaths=/etc/invariance-swarm/codex-worker/auth.json:",
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK",
    ):
        assert setting in unit
    assert "ReadWritePaths=/etc/invariance-swarm/codex-worker" not in unit
    assert "MemoryDenyWriteExecute=true" not in unit
    assert "Repository access remains read-only and networkless" in unit


def test_installer_is_explicit_and_preserves_existing_credentials():
    path = ROOT / "systemd/install-alpha-reviewers.sh"
    subprocess.run(["bash", "-n", str(path)], check=True)
    script = path.read_text()
    assert "start=false" in script
    assert "if $start; then" in script
    assert 'test ! -L "$environment"' in script
    assert 'test ! -L "$runtime/auth.json"' in script
    assert 'if [[ ! -e "$runtime/auth.json" ]]' in script
    assert "root:root:600" in script
    assert "cp " not in script
    assert "disable" not in script
