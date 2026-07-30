from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import shutil
import socketserver
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

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
    ) -> dict[str, Any]:
        if isinstance(args, (str, bytes)) or not args:
            raise BrokerError("Broker commands must be argument arrays.")
        try:
            with (
                stdin_path.open("rb")
                if stdin_path is not None
                else open(os.devnull, "rb")
            ) as stdin:
                completed = subprocess.run(
                    tuple(args),
                    cwd=cwd,
                    env={
                        "PATH": (
                            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:"
                            "/sbin:/bin"
                        ),
                        "LANG": "C.UTF-8",
                        "LC_ALL": "C.UTF-8",
                        "DOCKER_CONFIG": str(_DOCKER_CONFIG),
                    },
                    stdin=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            return {
                "args": list(args),
                "return_code": 124,
                "stdout": _bounded_text(exc.stdout),
                "stderr": _bounded_text(exc.stderr),
            }
        return {
            "args": list(args),
            "return_code": completed.returncode,
            "stdout": completed.stdout[-_MAX_OUTPUT:],
            "stderr": completed.stderr[-_MAX_OUTPUT:],
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
        if payload.contract.operation == "preflight-invariance-postgres":
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
        target_state = (
            "absent"
            if not self._postgres_root.exists()
            else "empty"
            if self._postgres_root.is_dir()
            and not any(self._postgres_root.iterdir())
            else "occupied"
        )
        checks = {
            "not_root_filesystem_constrained": storage.free >= 50 * 1024**3,
            "memory_sufficient": memory_bytes >= 8 * 1024**3,
            "cpu_sufficient": (os.cpu_count() or 0) >= 4,
            "docker_available": docker["return_code"] == 0,
            "compose_available": compose["return_code"] == 0,
            "source_repository_available": source_commit["return_code"] == 0,
            "target_directory_available": target_state in {"absent", "empty"},
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
