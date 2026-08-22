from pathlib import Path
from unittest.mock import patch

from swarm_worker.fleet_watchdog import WatchdogSettings, cycle


def settings(tmp_path: Path) -> WatchdogSettings:
    token = tmp_path / "telegram-token"
    token.write_text("1234567890:telegram-token-value", encoding="utf-8")
    return WatchdogSettings(
        targets="vm1-developer=100.64.0.1:22,vm2-deployment=100.64.0.2:8787",
        telegram_token_file=token,
        founder_chat_id=12345,
        failure_samples=3,
        recovery_samples=3,
        state_path=tmp_path / "state.json",
    )


def test_transient_failure_is_silent_and_sustained_failure_deduplicates(
    tmp_path: Path,
) -> None:
    configured = settings(tmp_path)
    with patch("swarm_worker.fleet_watchdog.check_target", return_value=False):
        assert cycle(configured) == []
        assert cycle(configured) == []
        notifications = cycle(configured)
        assert {item["machine"] for item in notifications} == {
            "vm1-developer",
            "vm2-deployment",
        }
        assert cycle(configured) == []


def test_recovery_is_sustained_and_emitted_once(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    with patch("swarm_worker.fleet_watchdog.check_target", return_value=False):
        for _ in range(3):
            cycle(configured)
    with patch("swarm_worker.fleet_watchdog.check_target", return_value=True):
        assert cycle(configured) == []
        assert cycle(configured) == []
        recovered = cycle(configured)
        assert all(item["state"] == "recovered" for item in recovered)
        assert cycle(configured) == []
