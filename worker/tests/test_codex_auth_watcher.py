import subprocess
from pathlib import Path

from swarm_worker.codex_auth_watcher import (
    AUTH_FAILURES,
    CodexRuntime,
    _retry_pending,
    _safe_summary,
)


def test_retry_is_pending_only_after_unacknowledged_request() -> None:
    assert _retry_pending(
        {
            "retry_requested_at": "2026-09-27T10:01:00Z",
            "retry_acknowledged_at": "2026-09-27T10:00:00Z",
        }
    )
    assert not _retry_pending(
        {
            "retry_requested_at": "2026-09-27T10:01:00Z",
            "retry_acknowledged_at": "2026-09-27T10:02:00Z",
        }
    )


def test_probe_requires_real_exec_and_classifies_auth_failure(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[-2:] == ["login", "status"]:
            return subprocess.CompletedProcess(command, 0, "Logged in", "")
        return subprocess.CompletedProcess(
            command, 1, "", "401 Unauthorized: refresh token rejected"
        )

    monkeypatch.setattr(subprocess, "run", run)
    runtime = CodexRuntime(Path("/usr/bin/codex"), tmp_path, "gpt-test")

    result = runtime.probe()

    assert not result.healthy
    assert result.authentication_failed
    probe = next(command for command in calls if "exec" in command)
    assert probe[0:2] == ["/usr/bin/flock", "-s"]
    assert all(marker.lower() == marker for marker in AUTH_FAILURES)


def test_device_login_keeps_exclusive_credential_lock(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    class Process:
        stdout = None

    def popen(command, **kwargs):
        calls.append(command)
        return Process()

    monkeypatch.setattr(subprocess, "Popen", popen)
    runtime = CodexRuntime(Path("/usr/bin/codex"), tmp_path, "gpt-test")

    runtime.begin_device_login()

    assert calls[0][0:2] == ["/usr/bin/flock", "-x"]


def test_safe_summary_does_not_echo_named_token_fields() -> None:
    summary = _safe_summary(
        "refresh_token access_token id_token sk-example-secret-value "
        "eyJexample.long.token.material"
    )
    assert "refresh_token" not in summary
    assert "access_token" not in summary
    assert "id_token" not in summary
    assert "sk-example" not in summary
    assert "eyJexample" not in summary
