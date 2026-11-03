from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_vps1_observer_profile_is_canonical() -> None:
    module = runpy.run_path(str(ROOT / "scripts/ops004_bootstrap.py"))
    assert module["PROFILES"]["vps1"] == {
        "package": "vps1-execution-fleet-observer",
        "slug": "vps1-execution-fleet-observer",
        "display_name": "VPS1 Execution Fleet Observer",
        "machine": "vps1-execution",
    }
    assert "exec1" not in module["PROFILES"]
    assert "exec2" not in module["PROFILES"]


def test_vps1_installer_is_fail_closed_and_location_bound() -> None:
    installer = ROOT / "systemd/install-vps1-execution-host.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    source = installer.read_text(encoding="utf-8")
    assert 'egress_country" != "NG"' in source
    assert "ip link show tailscale0" in source
    assert 'tailscale status --json' in source
    assert 'tailscale_backend" != "Running"' in source
    assert 'tailscale ip -4' in source
    assert '"management_ipv4": sys.argv[7]' in source
    assert "/home/omenka/.ssh/authorized_keys" in source
    assert "/etc/ssh/sshd_config.d/00-invariance-hardening.conf" in source
    assert "PermitRootLogin no" in source
    assert "PasswordAuthentication no" in source
    assert "KbdInteractiveAuthentication no" in source
    assert "AllowUsers omenka" in source
    assert "sshd -t" in source
    assert "usermod -L root" in source
    assert "ufw allow in on tailscale0 to any port 22 proto tcp" in source
    assert '"capital_authority": False' in source
    assert '"order_authority": False' in source
    assert '"execution_runtime_enabled": False' in source
    assert "BYBIT_API_KEY" not in source
    assert "BINANCE_API_KEY" not in source
    assert "systemctl enable --now invariance-swarm-execution" not in source
