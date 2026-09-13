from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_exec2_observer_profile_is_canonical() -> None:
    module = runpy.run_path(str(ROOT / "scripts/ops004_bootstrap.py"))
    assert module["PROFILES"]["exec2"] == {
        "package": "exec2-lagos-fleet-observer",
        "slug": "exec2-lagos-fleet-observer",
        "display_name": "EXEC2 Lagos Fleet Observer",
        "machine": "exec2-lagos",
    }


def test_exec2_installer_is_fail_closed_and_location_bound() -> None:
    installer = ROOT / "systemd/install-exec2-lagos-host.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    source = installer.read_text(encoding="utf-8")
    assert 'egress_country" != "NG"' in source
    assert "ip link show tailscale0" in source
    assert "ufw allow in on tailscale0 to any port 22 proto tcp" in source
    assert '"capital_authority": False' in source
    assert '"order_authority": False' in source
    assert '"venue_credentials_installed": False' in source
    assert '"execution_runtime_enabled": False' in source
    assert "BYBIT_API_KEY" not in source
    assert "BINANCE_API_KEY" not in source
