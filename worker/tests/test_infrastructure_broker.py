import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from swarm_worker.infrastructure.broker import (
    BrokerError,
    FixedRunner,
    InfrastructureBroker,
)
from swarm_worker.infrastructure.packages import load_runbook_package
from swarm_worker.infrastructure.postgres_deployment import (
    PostgresDeploymentManager,
)
from swarm_worker.infrastructure.runbooks import RunbookError, load_runbook
from swarm_worker.models import BrokerTicketPayload, BrokerTicketResponse

SECRET = "broker-test-secret-value-1234567890"
UTC = timezone.utc
TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AGENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakeRunner:
    def __init__(self, *, unhealthy_after_restart: bool = False) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.unhealthy_after_restart = unhealthy_after_restart
        self.restarted = False

    def run(self, args, **kwargs):
        assert not isinstance(args, str)
        command = tuple(args)
        self.commands.append(command)
        if command[:4] == ("docker", "compose", "restart", "--timeout"):
            self.restarted = True
        if command[:2] == ("docker", "inspect"):
            unhealthy = self.unhealthy_after_restart and self.restarted
            return {
                "args": list(args),
                "return_code": 0,
                "stdout": "exited unhealthy" if unhealthy else "running healthy",
                "stderr": "",
            }
        if command[:4] == ("docker", "exec", "swarm-redis", "redis-cli"):
            return {
                "args": list(args),
                "return_code": 0,
                "stdout": "PONG\n",
                "stderr": "",
            }
        if command[:2] == ("docker", "compose") and command[-2:] == ("up", "-d"):
            return {"args": list(args), "return_code": 0, "stdout": "", "stderr": ""}
        failed = (
            self.unhealthy_after_restart
            and self.restarted
            and command[:3] == ("python3", "-c", command[2])
        )
        return {
            "args": list(args),
            "return_code": 1 if failed else 0,
            "stdout": "ok",
            "stderr": "",
        }


def ticket(
    operation: str,
    *,
    risk: int,
    task_type: str,
    runbook: str = "vm2-infrastructure",
    target: str = "vm2-control-plane",
    parameters: dict | None = None,
    package_digest: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    payload = BrokerTicketPayload(
        schema_version=1,
        task_id=TASK_ID,
        task_number="INFRA-1",
        attempt_number=1,
        agent_id=AGENT_ID,
        machine="vm2-deployment",
        task_type=task_type,
        risk_level=risk,
        plan_digest="a" * 64,
        contract={
            "runbook": runbook,
            "runbook_version": "1.0.0",
            "operation": operation,
            "target": target,
            "parameters": parameters or {},
            **(
                {
                    "package_name": runbook,
                    "package_version": "1.0.0",
                    "package_digest": package_digest,
                }
                if package_digest is not None
                else {}
            ),
        },
        nonce=hashlib.sha256(operation.encode()).hexdigest(),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return BrokerTicketResponse(
        payload=payload,
        signature=hmac.new(SECRET.encode(), canonical, hashlib.sha256).hexdigest(),
    ).model_dump(mode="json")


def broker(tmp_path: Path, runner: FakeRunner) -> InfrastructureBroker:
    runtime = tmp_path / "runtime"
    runtime.mkdir(exist_ok=True)
    backups = runtime / "backups"
    backups.mkdir(exist_ok=True)
    (backups / "swarm-control.dump").write_bytes(b"test backup")
    return InfrastructureBroker(
        secret=SECRET,
        ledger_path=tmp_path / "consumed.json",
        runner=runner,
        effective_uid=0,
        runtime_path=runtime,
        backup_path=backups,
        postgres_root=tmp_path / "postgres",
        research_repository=tmp_path / "invariance_research",
        systemd_path=tmp_path / "systemd",
        sleep=lambda _: None,
    )


def platform_digest() -> str:
    root = Path(__file__).parents[1]
    return load_runbook_package(
        root / "runbook-packages", "vm2-platform-operations"
    ).manifest_digest


def test_packaged_health_uses_fixed_service_catalog(tmp_path: Path) -> None:
    runner = FakeRunner()
    result = broker(tmp_path, runner).execute(
        ticket(
            "verify-docker-service",
            risk=0,
            task_type="infrastructure_observation",
            runbook="vm2-platform-operations",
            target="vm2-production",
            parameters={"service": "api"},
            package_digest=platform_digest(),
        )
    )
    assert result.success is True
    assert result.post_state == {
        "service": "api",
        "container": "swarm-api",
        "healthy": True,
        "state": "running healthy",
    }
    assert runner.commands == [
        (
            "docker",
            "inspect",
            "swarm-api",
            "--format",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
        )
    ]


def test_packaged_health_supports_rehearsal_service_catalog(tmp_path: Path) -> None:
    runner = FakeRunner()
    rehearsal = broker(tmp_path, runner)
    rehearsal._platform_services = {
        "api": ("api", tmp_path / "rehearsal", "hermes-rehearsal-api")
    }
    result = rehearsal.execute(
        ticket(
            "verify-docker-service",
            risk=0,
            task_type="infrastructure_observation",
            runbook="vm2-platform-operations",
            target="vm2-production",
            parameters={"service": "api"},
            package_digest=platform_digest(),
        )
    )
    assert result.success is True
    assert result.post_state["container"] == "hermes-rehearsal-api"
    assert runner.commands[0][2] == "hermes-rehearsal-api"


def test_packaged_restart_rolls_back_with_fixed_compose_command(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(unhealthy_after_restart=True)
    result = broker(tmp_path, runner).execute(
        ticket(
            "restart-docker-service",
            risk=3,
            task_type="infrastructure_operation",
            runbook="vm2-platform-operations",
            target="vm2-production",
            parameters={"service": "redis"},
            package_digest=platform_digest(),
        )
    )
    assert result.success is False
    assert result.rollback is not None
    assert (
        "docker",
        "compose",
        "up",
        "-d",
        "--no-deps",
        "--force-recreate",
        "redis",
    ) in runner.commands


def test_packaged_restart_waits_for_transitional_health(tmp_path: Path) -> None:
    class TransitionalRunner(FakeRunner):
        def __init__(self) -> None:
            super().__init__()
            self.post_restart_checks = 0

        def run(self, args, **kwargs):
            command = tuple(args)
            if command[:2] == ("docker", "inspect") and self.restarted:
                self.commands.append(command)
                self.post_restart_checks += 1
                state = (
                    "running starting"
                    if self.post_restart_checks == 1
                    else "running healthy"
                )
                return {
                    "args": list(args),
                    "return_code": 0,
                    "stdout": state,
                    "stderr": "",
                }
            return super().run(args, **kwargs)

    runner = TransitionalRunner()
    result = broker(tmp_path, runner).execute(
        ticket(
            "restart-docker-service",
            risk=3,
            task_type="infrastructure_operation",
            runbook="vm2-platform-operations",
            target="vm2-production",
            parameters={"service": "api"},
            package_digest=platform_digest(),
        )
    )
    assert result.success is True
    assert runner.post_restart_checks == 2
    assert result.rollback is None


def test_packaged_operation_rejects_digest_or_parameter_tampering(
    tmp_path: Path,
) -> None:
    with pytest.raises(BrokerError):
        broker(tmp_path, FakeRunner()).execute(
            ticket(
                "verify-docker-service",
                risk=0,
                task_type="infrastructure_observation",
                runbook="vm2-platform-operations",
                target="vm2-production",
                parameters={"service": "api"},
                package_digest="0" * 64,
            )
        )


def test_observation_is_read_only_and_replay_is_rejected(tmp_path: Path) -> None:
    runner = FakeRunner()
    instance = broker(tmp_path, runner)
    document = ticket(
        "observe-control-plane",
        risk=0,
        task_type="infrastructure_observation",
    )
    result = instance.execute(document)
    assert result.success is True
    assert result.pre_state["latest_backup"]["integrity_ok"] is True
    assert result.pre_state["latest_backup"]["integrity_error"] == ""
    assert result.pre_state["latest_backup"]["fresh"] is True
    assert result.pre_state["latest_backup"]["sha256"] == hashlib.sha256(
        b"test backup"
    ).hexdigest()
    assert (
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "pg_restore",
        "--list",
    ) in runner.commands
    assert not any("restart" in command for command in runner.commands)
    with pytest.raises(BrokerError, match="already consumed"):
        instance.execute(document)


def test_tampered_and_expired_ticket_are_rejected(tmp_path: Path) -> None:
    document = ticket(
        "observe-control-plane",
        risk=0,
        task_type="infrastructure_observation",
    )
    document["payload"]["risk_level"] = 1
    with pytest.raises(BrokerError, match="signature"):
        broker(tmp_path, FakeRunner()).execute(document)

    document = ticket(
        "observe-control-plane",
        risk=0,
        task_type="infrastructure_observation",
    )
    document["payload"]["issued_at"] = (
        datetime.now(UTC) - timedelta(seconds=2)
    ).isoformat()
    document["payload"]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    payload = BrokerTicketPayload.model_validate(document["payload"])
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    document["signature"] = hmac.new(
        SECRET.encode(), canonical, hashlib.sha256
    ).hexdigest()
    with pytest.raises(BrokerError, match="expired"):
        broker(tmp_path, FakeRunner()).execute(document)


def test_postgres_preflight_is_read_only_and_reports_tls_blocker(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    result = broker(tmp_path, runner).execute(
        ticket(
            "preflight-invariance-postgres",
            risk=0,
            task_type="infrastructure_observation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    assert result.operation == "preflight-invariance-postgres"
    assert result.pre_state["public_tls"]["ready"] is False
    assert (
        "git",
        "-c",
        f"safe.directory={tmp_path / 'invariance_research'}",
        "rev-parse",
        "HEAD",
    ) in runner.commands
    assert not any(
        {"up", "restart", "install", "push"} & set(command)
        for command in runner.commands
    )


def test_postgres_preflight_accepts_exact_preprovisioned_layout(
    tmp_path: Path,
) -> None:
    root = tmp_path / "postgres"
    root.mkdir()
    for name in (
        "archive",
        "backups",
        "bin",
        "certs",
        "conf",
        "cutover",
        "data",
        "init",
        "logs",
        "pgbouncer",
        "schema",
    ):
        path = root / name
        path.mkdir()
        if name in {"archive", "data", "logs"}:
            path.chmod(0o750)
    instance = InfrastructureBroker(
        secret=SECRET,
        ledger_path=tmp_path / "consumed.json",
        runner=FakeRunner(),
        effective_uid=0,
        runtime_path=tmp_path,
        backup_path=tmp_path / "backups",
        postgres_root=root,
        research_repository=tmp_path / "invariance_research",
        systemd_path=tmp_path / "systemd",
        sleep=lambda _: None,
    )

    result = instance.execute(
        ticket(
            "preflight-invariance-postgres",
            risk=0,
            task_type="infrastructure_observation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    assert result.success is True
    assert result.pre_state["target_directory"] == "preprovisioned"


def test_postgres_preflight_accepts_digest_bound_staged_layout(
    tmp_path: Path,
) -> None:
    root = tmp_path / "postgres"
    PostgresDeploymentManager(
        root,
        postgres_uid=os.geteuid(),
        postgres_gid=os.getegid(),
    ).stage()
    instance = InfrastructureBroker(
        secret=SECRET,
        ledger_path=tmp_path / "consumed.json",
        runner=FakeRunner(),
        effective_uid=0,
        runtime_path=tmp_path,
        backup_path=tmp_path / "backups",
        postgres_root=root,
        research_repository=tmp_path / "invariance_research",
        systemd_path=tmp_path / "systemd",
        sleep=lambda _: None,
    )

    result = instance.execute(
        ticket(
            "preflight-invariance-postgres",
            risk=0,
            task_type="infrastructure_observation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    assert result.success is True
    assert result.pre_state["target_directory"] == "staged"


def test_postgres_stage_uses_compiled_private_template(tmp_path: Path) -> None:
    result = broker(tmp_path, FakeRunner()).execute(
        ticket(
            "stage-invariance-postgres",
            risk=2,
            task_type="infrastructure_operation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    assert result.success is True
    assert result.action is not None
    assert result.action["public_access"] is False
    assert result.post_state is not None
    assert result.post_state["staged"] is True
    assert "PASSWORD" not in json.dumps(result.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("operation", "risk", "task_type"),
    [
        ("start-invariance-postgres-private", 3, "infrastructure_operation"),
        ("initialize-invariance-schema", 3, "infrastructure_operation"),
        ("verify-invariance-postgres", 0, "infrastructure_observation"),
        ("prepare-invariance-cutover", 0, "infrastructure_observation"),
    ],
)
def test_postgres_phases_use_only_fixed_broker_commands(
    tmp_path: Path,
    operation: str,
    risk: int,
    task_type: str,
) -> None:
    runner = FakeRunner()
    instance = broker(tmp_path, runner)
    result = instance.execute(
        ticket(
            operation,
            risk=risk,
            task_type=task_type,
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    if operation == "prepare-invariance-cutover":
        assert result.success is True
        assert result.post_state["ready"] is False
        assert result.post_state["public_access_changed"] is False
    elif operation == "verify-invariance-postgres":
        assert result.success is False
    else:
        assert result.success is True
    if operation == "start-invariance-postgres-private":
        assert any(
            command[-8:]
            == (
                "-h",
                "127.0.0.1",
                "-p",
                "5432",
                "-U",
                "invariance_app",
                "-d",
                "invariance_research",
            )
            for command in runner.commands
        )
    serialized = json.dumps(result.model_dump(mode="json"))
    assert "INVARIANCE_OWNER_PASSWORD" not in serialized
    assert "postgresql://invariance_owner:" not in serialized
    if operation == "initialize-invariance-schema":
        assert any(
            command[-6:]
            == (
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "--wait",
                "postgres",
            )
            for command in runner.commands
        )
        assert any(
            "PGPASSWORD" in command
            and "invariance_owner" in command
            and "--env-file" in command
            for command in runner.commands
        )
    assert all(not isinstance(command, str) for command in runner.commands)


def test_backup_phase_installs_timer_and_runs_isolated_restore_drill(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    instance = broker(tmp_path, runner)
    instance.execute(
        ticket(
            "stage-invariance-postgres",
            risk=2,
            task_type="infrastructure_operation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )
    backup = tmp_path / "postgres" / "backups" / "test.dump"
    backup.write_bytes(b"reviewed backup")

    result = broker(tmp_path, runner).execute(
        ticket(
            "configure-invariance-backups",
            risk=3,
            task_type="infrastructure_operation",
            runbook="vm2-postgres-deployment",
            target="vm2-invariance-postgres",
        )
    )

    assert result.success is True
    assert result.post_state["restore_drill"]["success"] is True
    assert result.post_state["restore_drill"]["database"] == (
        "hermes_restore_drill"
    )
    assert (tmp_path / "systemd" / "invariance-postgres-backup.timer").is_file()


def test_fixed_runner_redacts_secret_environment_output(tmp_path: Path) -> None:
    secret = "postgresql://owner:very-secret-value@example/database"
    result = FixedRunner().run(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ['DATABASE_URL'])",
        ],
        cwd=tmp_path,
        extra_env={"DATABASE_URL": secret},
    )

    assert result["return_code"] == 0
    assert secret not in json.dumps(result)
    assert "[REDACTED]" in result["stdout"]


def test_restart_uses_exact_action_and_rolls_back_failed_health(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(unhealthy_after_restart=True)
    result = broker(tmp_path, runner).execute(
        ticket(
            "restart-control-plane-api",
            risk=3,
            task_type="infrastructure_operation",
        )
    )
    assert result.success is False
    assert (
        "docker",
        "compose",
        "restart",
        "--timeout",
        "30",
        "api",
    ) in runner.commands
    assert any(command[:4] == ("docker", "compose", "up", "-d") for command in runner.commands)
    assert result.rollback_state is not None


def test_broker_refuses_non_root(tmp_path: Path) -> None:
    with pytest.raises(BrokerError, match="root"):
        InfrastructureBroker(
            secret=SECRET,
            ledger_path=tmp_path / "ledger.json",
            effective_uid=1000,
        )


def test_fixed_runner_converts_timeout_to_bounded_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args, **kwargs):
        assert kwargs["env"]["DOCKER_CONFIG"] == (
            "/run/invariance-swarm-infrastructure/docker-config"
        )
        assert "SWARM_AGENT_TOKEN" not in kwargs["env"]
        raise subprocess.TimeoutExpired(
            cmd=["docker", "compose", "restart"],
            timeout=1,
            output=b"partial output",
            stderr=b"partial error",
        )

    monkeypatch.setattr(subprocess, "run", timeout)
    result = FixedRunner().run(["docker", "compose", "restart"], timeout=1)
    assert result["return_code"] == 124
    assert result["stdout"] == "partial output"
    assert result["stderr"] == "partial error"


def test_runbooks_reject_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "schema_version: 1\nname: vm2-infrastructure\nversion: 1.0.0\n"
        "operations: []\ncommand: sudo anything\n",
        encoding="utf-8",
    )
    with pytest.raises(RunbookError):
        load_runbook(path)
