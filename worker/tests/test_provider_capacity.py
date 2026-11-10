from datetime import UTC, datetime

from swarm_worker.models import StepExecutionResult
from swarm_worker.provider_capacity import detect_provider_capacity


def test_discovery_usage_limit_is_structured_for_global_circuit(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "discovery.stderr.log").write_text(
        "You've hit your usage limit. Retry in 45 minutes.\n", encoding="utf-8"
    )
    now = datetime.now(UTC)
    step = StepExecutionResult(
        name="alpha-intelligence",
        success=False,
        return_code=1,
        started_at=now,
        ended_at=now,
        duration_seconds=0.1,
        stdout_log="logs/discovery.stdout.log",
        stderr_log="logs/discovery.stderr.log",
    )

    assert detect_provider_capacity(
        [step], tmp_path, {"alpha-intelligence": "codex"}
    ) == {
        "provider": "codex",
        "failure_summary": "You've hit your usage limit. Retry in 45 minutes.",
        "retry_after_seconds": 2700,
    }


def test_non_capacity_failure_does_not_open_provider_circuit(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "review.stderr.log").write_text(
        "Schema validation failed.\n", encoding="utf-8"
    )
    now = datetime.now(UTC)
    step = StepExecutionResult(
        name="independent-strategy-review",
        success=False,
        return_code=1,
        started_at=now,
        ended_at=now,
        duration_seconds=0.1,
        stdout_log="logs/review.stdout.log",
        stderr_log="logs/review.stderr.log",
    )

    assert (
        detect_provider_capacity(
            [step], tmp_path, {"independent-strategy-review": "codex"}
        )
        is None
    )
