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
    assert engineering._validator._step_timeout_seconds == 2400.0


def test_engineering_validation_timeout_uses_worker_setting(tmp_path: Path) -> None:
    from swarm_worker.config import WorkerSettings

    settings = WorkerSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token="a" * 20,
        swarm_engineering_validation_timeout_seconds=3600,
    )
    executor = RestrictedExecutor(
        codex_home=tmp_path,
        codex_model="test-model",
        engineering_timeout_seconds=7200,
        heartbeat_interval_seconds=5,
        settings=settings,
    )

    assert executor._engineering._validator._step_timeout_seconds == 3600.0
