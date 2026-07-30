from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import shutil
import socket
import socketserver
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from swarm_worker.infrastructure.postgres_deployment import (
    PostgresDeploymentManager,
)
from swarm_worker.models import (
    BrokerExecutionResult,
    BrokerTicketResponse,
)

_RUNTIME = Path("/srv/invariance/swarm/control-plane-runtime")
_BACKUPS = _RUNTIME / "backups"
_DOCKER_CONFIG = Path("/run/invariance-swarm-infrastructure/docker-config")
_MAX_OUTPUT = 16_000
_MAX_BACKUP_AGE_SECONDS = 7 * 24 * 60 * 60
_POSTGRES_ROOT = Path("/srv/invariance/postgres")
_RESEARCH_REPOSITORY = Path("/srv/invariance/invariance_research")
UTC = timezone.utc


class BrokerError(Exception):
    """A ticket or reviewed broker operation failed closed."""


class FixedRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path = _RUNTIME,
        timeout: float = 60,
        stdin_path: Path | None = None,
        stdout_path: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if isinstance(args, (str, bytes)) or not args:
            raise BrokerError("Broker commands must be argument arrays.")
        environment = {
            "PATH": (
                "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:"
                "/sbin:/bin"
            ),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "DOCKER_CONFIG": str(_DOCKER_CONFIG),
        }
        if extra_env:
            environment.update(extra_env)
        try:
            with ExitStack() as stack:
                stdin = (
                    stack.enter_context(stdin_path.open("rb"))
                    if stdin_path is not None
                    else subprocess.DEVNULL
                )
                stdout = (
                    stack.enter_context(stdout_path.open("wb"))
                    if stdout_path is not None
                    else subprocess.PIPE
                )
                completed = subprocess.run(
                    tuple(args),
                    cwd=cwd,
                    env=environment,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            return {
                "args": list(args),
                "return_code": 124,
                "stdout": _redact(_bounded_text(exc.stdout), extra_env),
                "stderr": _redact(_bounded_text(exc.stderr), extra_env),
            }
        return {
            "args": list(args),
            "return_code": completed.returncode,
            "stdout": _redact(_bounded_text(completed.stdout), extra_env),
            "stderr": _redact(_bounded_text(completed.stderr), extra_env),
        }


class InfrastructureBroker:
    def __init__(
        self,
        *,
        secret: str,
        ledger_path: Path,
        runner: FixedRunner | None = None,
        effective_uid: int | None = None,
        runtime_path: Path = _RUNTIME,
        backup_path: Path = _BACKUPS,
        postgres_root: Path = _POSTGRES_ROOT,
        research_repository: Path = _RESEARCH_REPOSITORY,
        systemd_path: Path = Path("/etc/systemd/system"),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if len(secret) < 32:
            raise BrokerError("Broker secret is unavailable or too short.")
        if (os.geteuid() if effective_uid is None else effective_uid) != 0:
            raise BrokerError("Infrastructure broker must run as root.")
        self._secret = secret
        self._ledger_path = ledger_path
        self._runner = runner or FixedRunner()
        self._runtime_path = runtime_path
        self._backup_path = backup_path
        self._postgres_root = postgres_root
        self._research_repository = research_repository
        self._systemd_path = systemd_path
        self._sleep = sleep
        self._consumed = self._load_ledger()

    def execute(self, document: dict[str, Any]) -> BrokerExecutionResult:
        try:
            ticket = BrokerTicketResponse.model_validate(document)
        except ValidationError as exc:
            raise BrokerError("Broker ticket is invalid.") from exc
        canonical = json.dumps(
            ticket.payload.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        expected = hmac.new(
            self._secret.encode(), canonical, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, ticket.signature):
            raise BrokerError("Broker ticket signature is invalid.")
        now = datetime.now(UTC)
        if ticket.payload.expires_at <= now:
            raise BrokerError("Broker ticket has expired.")
        if ticket.payload.nonce in self._consumed:
            raise BrokerError("Broker ticket was already consumed.")
        self._validate_operation(ticket)
        self._consume(ticket.payload.nonce)
        return self._execute_operation(ticket, now)

    def _validate_operation(self, ticket: BrokerTicketResponse) -> None:
        payload = ticket.payload
        operation = payload.contract.operation
        expected = {
            "observe-control-plane": ("infrastructure_observation", 0),
            "restart-control-plane-api": ("infrastructure_operation", 3),
            "preflight-invariance-postgres": (
                "infrastructure_observation",
                0,
            ),
            "stage-invariance-postgres": ("infrastructure_operation", 2),
            "start-invariance-postgres-private": (
                "infrastructure_operation",
                3,
            ),
            "initialize-invariance-schema": ("infrastructure_operation", 3),
            "configure-invariance-backups": ("infrastructure_operation", 3),
            "verify-invariance-postgres": (
                "infrastructure_observation",
                0,
            ),
            "prepare-invariance-cutover": (
                "infrastructure_observation",
                0,
            ),
        }[operation]
        if (
            payload.machine != "vm2-deployment"
            or payload.task_type != expected[0]
            or payload.risk_level != expected[1]
            or payload.contract.parameters
        ):
            raise BrokerError("Ticket does not match the reviewed operation.")

    def _execute_operation(
        self,
        ticket: BrokerTicketResponse,
        started_at: datetime,
    ) -> BrokerExecutionResult:
        payload = ticket.payload
        operation = payload.contract.operation
        if operation == "stage-invariance-postgres":
            manager = PostgresDeploymentManager(
                self._postgres_root,
                postgres_uid=999 if os.geteuid() == 0 else os.geteuid(),
                postgres_gid=os.getegid(),
            )
            action = manager.stage()
            return BrokerExecutionResult(
                success=True,
                operation=payload.contract.operation,
                task_id=payload.task_id,
                attempt_number=payload.attempt_number,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                pre_state={"target_directory": "absent-or-reviewed"},
                action=action,
                post_state={
                    "staged": action["staged"],
                    "public_access": action["public_access"],
                    "metadata_sha256": action["metadata_sha256"],
                },
            )
        if operation in {
            "start-invariance-postgres-private",
            "initialize-invariance-schema",
            "configure-invariance-backups",
            "verify-invariance-postgres",
            "prepare-invariance-cutover",
        }:
            return self._execute_postgres_operation(
                operation,
                payload.task_id,
                payload.attempt_number,
                started_at,
            )
        if operation == "preflight-invariance-postgres":
            pre = self._preflight_invariance_postgres()
            return BrokerExecutionResult(
                success=bool(pre["ready"]),
                operation=payload.contract.operation,
                task_id=payload.task_id,
                attempt_number=payload.attempt_number,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                pre_state=pre,
                error=None if pre["ready"] else "Deployment preflight failed.",
            )
        pre = self._observe()
        if payload.contract.operation == "observe-control-plane":
            ended = datetime.now(UTC)
            return BrokerExecutionResult(
                success=bool(pre["healthy"]),
                operation=payload.contract.operation,
                task_id=payload.task_id,
                attempt_number=payload.attempt_number,
                started_at=started_at,
                ended_at=ended,
                pre_state=pre,
                error=None if pre["healthy"] else "Health verification failed.",
            )
        action = self._runner.run(
            ["docker", "compose", "restart", "--timeout", "30", "api"],
            cwd=self._runtime_path,
            timeout=90,
        )
        post = self._observe_until_healthy()
        rollback = None
        rollback_state = None
        success = action["return_code"] == 0 and bool(post["healthy"])
        if not success:
            rollback = self._runner.run(
                [
                    "docker",
                    "compose",
                    "up",
                    "-d",
                    "--no-deps",
                    "--force-recreate",
                    "api",
                ],
                cwd=self._runtime_path,
                timeout=120,
            )
            rollback_state = self._observe_until_healthy()
        return BrokerExecutionResult(
            success=success,
            operation=payload.contract.operation,
            task_id=payload.task_id,
            attempt_number=payload.attempt_number,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            pre_state=pre,
            action=action,
            post_state=post,
            rollback=rollback,
            rollback_state=rollback_state,
            error=None if success else "Restart transaction verification failed.",
        )

    def _execute_postgres_operation(
        self,
        operation: str,
        task_id: Any,
        attempt_number: int,
        started_at: datetime,
    ) -> BrokerExecutionResult:
        manager = PostgresDeploymentManager(
            self._postgres_root,
            postgres_uid=999 if os.geteuid() == 0 else os.geteuid(),
            postgres_gid=os.getegid(),
        )
        staged = manager.stage()
        if operation == "start-invariance-postgres-private":
            config = self._postgres_compose(["config", "--quiet"], timeout=30)
            pull = self._postgres_compose(["pull"], timeout=600)
            start = self._postgres_compose(["up", "-d"], timeout=300)
            post = self._postgres_health()
            success = all(
                item["return_code"] == 0
                for item in (config, pull, start)
            ) and post["healthy"]
            rollback = None
            if not success:
                rollback = self._postgres_compose(
                    ["stop", "--timeout", "30"], timeout=90
                )
            return self._postgres_result(
                operation,
                task_id,
                attempt_number,
                started_at,
                success=success,
                pre_state={"staged": staged["staged"]},
                action={"config": config, "pull": pull, "start": start},
                post_state=post,
                rollback=rollback,
                error=None if success else "Private startup verification failed.",
            )
        if operation == "initialize-invariance-schema":
            source = self._source_commit()
            environment = self._schema_environment()
            action = self._runner.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "deploy/docker-compose.worker.yml",
                    "-f",
                    str(
                        self._postgres_root
                        / "schema"
                        / "worker-network.override.yaml"
                    ),
                    "run",
                    "--rm",
                    "--no-deps",
                    "-e",
                    "DATABASE_PROVIDER=postgres",
                    "-e",
                    "DATABASE_URL",
                    "-e",
                    "POSTGRES_SCHEMA_AUTO_INIT=true",
                    "analysis-worker",
                    "npm",
                    "run",
                    "db:init:postgres",
                ],
                cwd=self._research_repository,
                timeout=1200,
                extra_env=environment,
            )
            marker = self._runner.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "-e",
                    f"PGAPPNAME={source}",
                    "postgres",
                    "psql",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "postgres",
                    "-d",
                    "invariance_research",
                ],
                cwd=self._postgres_root,
                timeout=60,
                stdin_path=self._postgres_root
                / "schema"
                / "001-broker-marker.sql",
            )
            success = action["return_code"] == 0 and marker["return_code"] == 0
            return self._postgres_result(
                operation,
                task_id,
                attempt_number,
                started_at,
                success=success,
                pre_state={"source_commit": source},
                action={"schema": action, "marker": marker},
                post_state={"schema_marker": marker["return_code"] == 0},
                error=None if success else "Schema initialization failed.",
            )
        if operation == "configure-invariance-backups":
            install = self._install_backup_units()
            backup = self._runner.run(
                [str(self._postgres_root / "bin" / "backup.sh")],
                cwd=self._postgres_root,
                timeout=900,
            )
            state = self._backup_state()
            restore = self._restore_drill()
            success = all(
                item["return_code"] == 0
                for item in (*install.values(), backup)
            ) and state["integrity_ok"] and restore["success"]
            return self._postgres_result(
                operation,
                task_id,
                attempt_number,
                started_at,
                success=success,
                action={
                    "unit_install": install,
                    "backup": backup,
                    "restore_drill": restore,
                },
                post_state=state | {"restore_drill": restore},
                error=None if success else "Backup configuration failed.",
            )
        if operation == "verify-invariance-postgres":
            post = self._postgres_health() | {"backup": self._backup_state()}
            success = post["healthy"] and post["backup"]["integrity_ok"]
            return self._postgres_result(
                operation,
                task_id,
                attempt_number,
                started_at,
                success=success,
                post_state=post,
                error=None if success else "Private deployment verification failed.",
            )
        cutover = self._cutover_readiness()
        return self._postgres_result(
            operation,
            task_id,
            attempt_number,
            started_at,
            success=True,
            post_state=cutover,
            error=None,
        )

    def _postgres_compose(
        self, args: Sequence[str], *, timeout: float
    ) -> dict[str, Any]:
        return self._runner.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(self._postgres_root / ".env.postgres"),
                *args,
            ],
            cwd=self._postgres_root,
            timeout=timeout,
        )

    def _postgres_health(self) -> dict[str, Any]:
        compose = self._postgres_compose(["ps", "--format", "json"], timeout=30)
        postgres = self._postgres_compose(
            [
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "invariance_research",
            ],
            timeout=30,
        )
        pgbouncer = self._postgres_compose(
            [
                "exec",
                "-T",
                "pgbouncer",
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-p",
                "6432",
                "-U",
                "invariance_app",
                "-d",
                "invariance_research",
            ],
            timeout=30,
        )
        return {
            "healthy": all(
                item["return_code"] == 0
                for item in (compose, postgres, pgbouncer)
            ),
            "compose": compose,
            "postgres": postgres,
            "pgbouncer": pgbouncer,
            "bindings": ["127.0.0.1:5432", "100.112.117.59:6432"],
            "public_access": False,
        }

    def _source_commit(self) -> str:
        result = self._runner.run(
            [
                "git",
                "-c",
                f"safe.directory={self._research_repository}",
                "rev-parse",
                "HEAD",
            ],
            cwd=self._research_repository,
            timeout=30,
        )
        if result["return_code"] != 0:
            raise BrokerError("Invariance source revision is unavailable.")
        return result["stdout"].strip()[:64]

    def _schema_environment(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in (self._postgres_root / ".env.postgres").read_text().splitlines():
            if line and not line.startswith("#"):
                name, separator, value = line.partition("=")
                if separator:
                    values[name] = value
        password = values.get("INVARIANCE_OWNER_PASSWORD")
        if not password:
            raise BrokerError("Schema owner credential is unavailable.")
        return {
            "INVARIANCE_STACK_ROOT": str(self._research_repository.parent),
            "DATABASE_URL": (
                "postgresql://invariance_owner:"
                f"{password}@postgres:5432/invariance_research"
            )
        }

    def _install_backup_units(self) -> dict[str, dict[str, Any]]:
        service = self._systemd_path / "invariance-postgres-backup.service"
        timer = self._systemd_path / "invariance-postgres-backup.timer"
        self._systemd_path.mkdir(parents=True, exist_ok=True)
        self._write_fixed_file(
            service,
            "[Unit]\nDescription=Invariance Postgres backup\n"
            "[Service]\nType=oneshot\n"
            f"ExecStart={self._postgres_root}/bin/backup.sh\n"
            "UMask=0077\nNoNewPrivileges=true\n",
        )
        self._write_fixed_file(
            timer,
            "[Unit]\nDescription=Schedule Invariance Postgres backups\n"
            "[Timer]\nOnCalendar=*-*-* 02:15:00 UTC\nPersistent=true\n"
            "RandomizedDelaySec=900\n"
            "[Install]\nWantedBy=timers.target\n",
        )
        service.chmod(0o644)
        timer.chmod(0o644)
        return {
            "daemon_reload": self._runner.run(
                ["systemctl", "daemon-reload"], timeout=30
            ),
            "timer": self._runner.run(
                [
                    "systemctl",
                    "enable",
                    "--now",
                    "invariance-postgres-backup.timer",
                ],
                timeout=60,
            ),
        }

    @staticmethod
    def _write_fixed_file(path: Path, content: str) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o644)

    def _backup_state(self) -> dict[str, Any]:
        backups = sorted(
            self._postgres_root.glob("backups/*.dump"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        timer = self._runner.run(
            [
                "systemctl",
                "is-enabled",
                "invariance-postgres-backup.timer",
            ],
            timeout=30,
        )
        if not backups:
            return {
                "integrity_ok": False,
                "timer_enabled": timer["return_code"] == 0,
                "latest_backup": None,
            }
        path = backups[0]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        integrity = self._runner.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "--list",
            ],
            cwd=self._postgres_root,
            timeout=60,
            stdin_path=path,
        )
        return {
            "integrity_ok": integrity["return_code"] == 0,
            "timer_enabled": timer["return_code"] == 0,
            "latest_backup": {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
            },
        }

    def _restore_drill(self) -> dict[str, Any]:
        backups = sorted(
            self._postgres_root.glob("backups/*.dump"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            return {"success": False, "reason": "no-backup"}
        database = "hermes_restore_drill"
        commands = [
            self._postgres_compose(
                [
                    "exec",
                    "-T",
                    "postgres",
                    "dropdb",
                    "--if-exists",
                    "-U",
                    "postgres",
                    database,
                ],
                timeout=60,
            ),
            self._postgres_compose(
                [
                    "exec",
                    "-T",
                    "postgres",
                    "createdb",
                    "-U",
                    "postgres",
                    database,
                ],
                timeout=60,
            ),
            self._runner.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_restore",
                    "-U",
                    "postgres",
                    "-d",
                    database,
                ],
                cwd=self._postgres_root,
                timeout=900,
                stdin_path=backups[0],
            ),
            self._postgres_compose(
                [
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    database,
                    "-Atc",
                    "SELECT count(*) FROM pg_catalog.pg_tables",
                ],
                timeout=60,
            ),
            self._postgres_compose(
                [
                    "exec",
                    "-T",
                    "postgres",
                    "dropdb",
                    "-U",
                    "postgres",
                    database,
                ],
                timeout=60,
            ),
        ]
        return {
            "success": all(item["return_code"] == 0 for item in commands),
            "return_codes": [item["return_code"] for item in commands],
            "database": database,
        }

    def _cutover_readiness(self) -> dict[str, Any]:
        cert = self._postgres_root / "certs" / "server.crt"
        key = self._postgres_root / "certs" / "server.key"
        egress = self._postgres_root / "conf" / "vercel-egress.txt"
        try:
            addresses = sorted(
                {
                    item[4][0]
                    for item in socket.getaddrinfo(
                        "db.invarianceresearch.xyz", 6432
                    )
                }
            )
        except OSError:
            addresses = []
        checks = {
            "dns_resolves": bool(addresses),
            "trusted_tls_material": cert.is_file() and key.is_file(),
            "vercel_egress_policy": egress.is_file()
            and bool(egress.read_text().strip()),
            "pgbouncer_client_tls": False,
            "source_migration_approved": False,
            "rollback_plan_approved": False,
        }
        return {
            "ready": all(checks.values()),
            "checks": checks,
            "dns_addresses": addresses[:10],
            "public_access_changed": False,
        }

    @staticmethod
    def _postgres_result(
        operation: str,
        task_id: Any,
        attempt_number: int,
        started_at: datetime,
        *,
        success: bool,
        pre_state: dict[str, Any] | None = None,
        action: dict[str, Any] | None = None,
        post_state: dict[str, Any] | None = None,
        rollback: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> BrokerExecutionResult:
        return BrokerExecutionResult(
            success=success,
            operation=operation,
            task_id=task_id,
            attempt_number=attempt_number,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            pre_state=pre_state or {},
            action=action,
            post_state=post_state,
            rollback=rollback,
            error=error,
        )

    def _preflight_invariance_postgres(self) -> dict[str, Any]:
        docker = self._runner.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            timeout=30,
        )
        compose = self._runner.run(
            ["docker", "compose", "version", "--short"],
            timeout=30,
        )
        source_commit = self._runner.run(
            [
                "git",
                "-c",
                f"safe.directory={self._research_repository}",
                "rev-parse",
                "HEAD",
            ],
            cwd=self._research_repository,
            timeout=30,
        )
        memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        storage = shutil.disk_usage(self._postgres_root.parent)
        port_state = {
            str(port): self._port_available(port) for port in (5432, 6432)
        }
        deployment = PostgresDeploymentManager(
            self._postgres_root,
            postgres_uid=999 if os.geteuid() == 0 else os.geteuid(),
            postgres_gid=os.getegid(),
        )
        target_state = (
            "absent"
            if not self._postgres_root.exists()
            else "empty"
            if self._postgres_root.is_dir()
            and not any(self._postgres_root.iterdir())
            else "preprovisioned"
            if deployment.is_preprovisioned()
            else "occupied"
        )
        checks = {
            "not_root_filesystem_constrained": storage.free >= 50 * 1024**3,
            "memory_sufficient": memory_bytes >= 8 * 1024**3,
            "cpu_sufficient": (os.cpu_count() or 0) >= 4,
            "docker_available": docker["return_code"] == 0,
            "compose_available": compose["return_code"] == 0,
            "source_repository_available": source_commit["return_code"] == 0,
            "target_directory_available": target_state
            in {"absent", "empty", "preprovisioned"},
            "postgres_port_available": port_state["5432"],
            "pgbouncer_port_available": port_state["6432"],
        }
        return {
            "ready": all(checks.values()),
            "checks": checks,
            "host": {
                "hostname": platform.node(),
                "kernel": platform.release(),
                "cpu_count": os.cpu_count(),
                "memory_bytes": memory_bytes,
            },
            "storage": {
                "total_bytes": storage.total,
                "free_bytes": storage.free,
            },
            "ports": port_state,
            "target_directory": target_state,
            "source_repository": {
                "path": str(self._research_repository),
                "commit": source_commit["stdout"].strip()[:64],
            },
            "docker": {
                "version": docker["stdout"].strip()[:100],
                "compose_version": compose["stdout"].strip()[:100],
            },
            "public_tls": {
                "ready": False,
                "reason": (
                    "The source runbook does not configure PgBouncer client TLS."
                ),
            },
        }

    @staticmethod
    def _port_available(port: int) -> bool:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                return False
        return True

    def _observe_until_healthy(self) -> dict[str, Any]:
        state = self._observe()
        for _ in range(5):
            if state["healthy"]:
                break
            self._sleep(5)
            state = self._observe()
        return state

    def _observe(self) -> dict[str, Any]:
        compose = self._runner.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=self._runtime_path,
            timeout=30,
        )
        postgres = self._runner.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                "swarm_app",
                "-d",
                "swarm_control",
            ],
            cwd=self._runtime_path,
            timeout=30,
        )
        redis = self._runner.run(
            ["docker", "compose", "exec", "-T", "redis", "redis-cli", "ping"],
            cwd=self._runtime_path,
            timeout=30,
        )
        health = self._runner.run(
            [
                "python3",
                "-c",
                (
                    "import urllib.request;"
                    "print(urllib.request.urlopen("
                    "'http://100.112.117.59:8787/health',timeout=5).status)"
                ),
            ],
            cwd=self._runtime_path,
            timeout=10,
        )
        disk = os.statvfs(self._runtime_path)
        backup_files = sorted(
            (
                path
                for path in self._backup_path.glob("*.dump")
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        latest = None
        if backup_files:
            path = backup_files[0]
            stat = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            integrity = self._runner.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_restore",
                    "--list",
                ],
                cwd=self._runtime_path,
                timeout=60,
                stdin_path=path,
            )
            age_seconds = max(
                0, int(datetime.now(UTC).timestamp() - stat.st_mtime)
            )
            latest = {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "age_seconds": age_seconds,
                "sha256": digest.hexdigest(),
                "integrity_return_code": integrity["return_code"],
                "integrity_ok": integrity["return_code"] == 0,
                "integrity_error": integrity["stderr"][-500:],
                "fresh": age_seconds <= _MAX_BACKUP_AGE_SECONDS,
            }
        healthy = all(
            item["return_code"] == 0 for item in (compose, postgres, redis, health)
        )
        backup_healthy = bool(
            latest and latest["integrity_ok"] and latest["fresh"]
        )
        return {
            "healthy": healthy and backup_healthy,
            "compose": compose,
            "postgres": postgres,
            "redis": redis,
            "api_health": health,
            "storage": {
                "total_bytes": disk.f_blocks * disk.f_frsize,
                "available_bytes": disk.f_bavail * disk.f_frsize,
            },
            "latest_backup": latest,
            "certificate": {"status": "not-configured"},
        }

    def _load_ledger(self) -> set[str]:
        if not self._ledger_path.exists():
            return set()
        try:
            value = json.loads(self._ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BrokerError("Broker replay ledger is invalid.") from exc
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise BrokerError("Broker replay ledger is invalid.")
        return set(value)

    def _consume(self, nonce: str) -> None:
        self._consumed.add(nonce)
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self._ledger_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(sorted(self._consumed)) + "\n", encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(self._ledger_path)


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            line = self.rfile.readline(1_000_001)
            if not line or len(line) > 1_000_000:
                raise BrokerError("Broker request size is invalid.")
            document = json.loads(line)
            result = self.server.broker.execute(document)  # type: ignore[attr-defined]
            response = {"ok": True, "result": result.model_dump(mode="json")}
        except Exception as exc:  # noqa: BLE001 - root broker boundary
            print(
                json.dumps(
                    {
                        "event": "broker_request_failed",
                        "error": type(exc).__name__,
                        "message": str(exc)[:500],
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
            response = {
                "ok": False,
                "error": type(exc).__name__,
                "message": str(exc)[:500],
            }
        self.wfile.write((json.dumps(response, sort_keys=True) + "\n").encode())


class _Server(socketserver.UnixStreamServer):
    allow_reuse_address = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--socket",
        type=Path,
        default=Path("/run/invariance-swarm-infrastructure/broker.sock"),
    )
    parser.add_argument(
        "--secret-file",
        type=Path,
        default=Path("/etc/invariance-swarm/infrastructure-broker.secret"),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("/var/lib/invariance-swarm-infrastructure/consumed.json"),
    )
    args = parser.parse_args()
    secret = args.secret_file.read_text(encoding="utf-8").strip()
    broker = InfrastructureBroker(secret=secret, ledger_path=args.ledger)
    args.socket.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    _DOCKER_CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    _DOCKER_CONFIG.chmod(0o700)
    if args.socket.exists():
        args.socket.unlink()
    with _Server(str(args.socket), _Handler) as server:
        server.broker = broker  # type: ignore[attr-defined]
        os.chmod(args.socket, 0o660)
        server.serve_forever()
    return 0


def _bounded_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return value[-_MAX_OUTPUT:]


def _redact(value: str, secrets: dict[str, str] | None) -> str:
    for secret in (secrets or {}).values():
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value
