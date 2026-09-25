from pathlib import Path

from swarm_worker.executors.restricted import RestrictedExecutor


def test_engineering_and_validation_use_distinct_umasks(tmp_path: Path) -> None:
    executor = RestrictedExecutor(
        codex_home=tmp_path,
        codex_model="test-model",
        engineering_timeout_seconds=60,
        heartbeat_interval_seconds=5,
    )

    engineering = executor._engineering
    assert engineering._runner._child_umask == 0o077
    assert engineering._validator._runner._child_umask == 0o022
    assert engineering._runner is not engineering._validator._runner
    assert engineering._validator._step_timeout_seconds == 1200.0
