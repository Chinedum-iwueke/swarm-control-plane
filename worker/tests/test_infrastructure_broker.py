import hashlib
import hmac
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from swarm_worker.infrastructure.broker import (
    BrokerError,
    FixedRunner,
    InfrastructureBroker,
)
from swarm_worker.infrastructure.runbooks import RunbookError, load_runbook
from swarm_worker.models import BrokerTicketPayload, BrokerTicketResponse

SECRET = "broker-test-secret-value-1234567890"
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
        if command[:4] == ("docker", "compose", "up", "-d"):
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
            "parameters": {},
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
        sleep=lambda _: None,
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
