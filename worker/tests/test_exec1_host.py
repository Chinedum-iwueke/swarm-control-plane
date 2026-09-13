from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_exec1_observer_profile_is_canonical() -> None:
    module = runpy.run_path(str(ROOT / "scripts/ops004_bootstrap.py"))
    profile = module["PROFILES"]["exec1"]
    assert profile == {
        "package": "exec1-fleet-observer",
        "slug": "exec1-fleet-observer",
        "display_name": "EXEC1 Fleet Observer",
        "machine": "exec1-execution",
    }


def test_exec1_installer_is_valid_and_does_not_enable_execution() -> None:
    installer = ROOT / "systemd/install-exec1-host.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    source = installer.read_text(encoding="utf-8")
    assert "capital_authority\": False" in source
    assert "order_authority\": False" in source
    assert "execution_runtime_enabled\": False" in source
    assert "BYBIT_API" not in source
    assert "BINANCE_API" not in source
    assert "systemctl enable --now invariance-swarm-execution" not in source
