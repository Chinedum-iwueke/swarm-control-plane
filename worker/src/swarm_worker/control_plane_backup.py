from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SCHEMA_VERSION = "control-plane-backup-v1.0.0"


class BackupSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWARM_BACKUP_", extra="ignore")

    runtime: Path = Path("/srv/invariance/swarm/control-plane-runtime")
    backup_directory: Path = Path(
        "/srv/invariance/swarm/control-plane-runtime/backups"
    )
    lock_path: Path = Path("/run/invariance-swarm/control-plane-backup.lock")
    database_container: str = Field(
        default="swarm-postgres", pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    database_user: str = Field(default="swarm_app", pattern=r"^[a-z_][a-z0-9_]*$")
    database_name: str = Field(
        default="swarm_control", pattern=r"^[a-z_][a-z0-9_]*$"
    )
    min_free_bytes: int = Field(default=2_147_483_648, ge=1_048_576)
    daily_generations: int = Field(default=7, ge=1, le=31)
    weekly_generations: int = Field(default=4, ge=1, le=12)
    monthly_generations: int = Field(default=6, ge=1, le=24)
    recent_generations: int = Field(default=2, ge=2, le=10)
    restore_image: str = Field(
        default="postgres:17-alpine", pattern=r"^[a-zA-Z0-9._:/-]+$"
    )


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["control-plane-backup-v1.0.0"] = SCHEMA_VERSION
    backup_id: str
    database: str
    filename: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    migration_marker: str = Field(min_length=1, max_length=200)
    started_at: datetime
    completed_at: datetime
    integrity_verified: bool
    host: str

    @model_validator(mode="after")
    def valid_times(self):
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("Backup timestamps must be timezone-aware.")
        if self.completed_at < self.started_at:
            raise ValueError("Backup completion precedes its start.")
        return self


def create_backup(settings: BackupSettings) -> BackupManifest:
    settings.backup_directory.mkdir(parents=True, exist_ok=True, mode=0o2750)
    if shutil.disk_usage(settings.backup_directory).free < settings.min_free_bytes:
        raise RuntimeError("Insufficient free space for a control-plane backup.")
    with _exclusive_lock(settings.lock_path):
        started = datetime.now(timezone.utc)
        identity = uuid.uuid4().hex[:12]
        stem = f"swarm_control_{started:%Y%m%dT%H%M%SZ}_{identity}"
        temporary = settings.backup_directory / f".{stem}.dump.partial"
        destination = settings.backup_directory / f"{stem}.dump"
        manifest_path = destination.with_suffix(".manifest.json")
        published = False
        try:
            with temporary.open("xb") as output:
                _run(
                    _database_exec(settings)
                    + [
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        f"--username={settings.database_user}",
                        f"--dbname={settings.database_name}",
                    ],
                    stdout=output,
                )
                output.flush()
                os.fsync(output.fileno())
            if temporary.stat().st_size == 0:
                raise RuntimeError("Control-plane backup is empty.")
            with temporary.open("rb") as source:
                _run(
                    _database_exec(settings) + ["pg_restore", "--list"],
                    stdin=source,
                    stdout=subprocess.DEVNULL,
                )
            migration = _run(
                _database_exec(settings)
                + [
                    "psql",
                    "--username",
                    settings.database_user,
                    "--dbname",
                    settings.database_name,
                    "--tuples-only",
                    "--no-align",
                    "--command",
                    "select version_num from alembic_version;",
                ],
                capture=True,
            ).strip()
            if not migration:
                raise RuntimeError("Database migration marker is unavailable.")
            digest = _sha256(temporary)
            completed = datetime.now(timezone.utc)
            manifest = BackupManifest(
                backup_id=identity,
                database=settings.database_name,
                filename=destination.name,
                byte_size=temporary.stat().st_size,
                sha256=digest,
                migration_marker=migration,
                started_at=started,
                completed_at=completed,
                integrity_verified=True,
                host=os.uname().nodename,
            )
            os.chmod(temporary, 0o640)
            os.replace(temporary, destination)
            _write_manifest(manifest_path, manifest)
            published = True
            apply_retention(settings)
            return manifest
        finally:
            temporary.unlink(missing_ok=True)
            if not published:
                destination.unlink(missing_ok=True)


def inspect_latest(
    settings: BackupSettings, *, verify_digest: bool = False
) -> dict[str, object]:
    records = _records(settings.backup_directory)
    if not records:
        return {"healthy": False, "reason": "no_verified_backup", "latest": None}
    manifest_path, manifest = records[0]
    dump = settings.backup_directory / manifest.filename
    healthy = dump.is_file() and dump.stat().st_size == manifest.byte_size
    reason = None if healthy else "backup_file_mismatch"
    if healthy and verify_digest and _sha256(dump) != manifest.sha256:
        healthy = False
        reason = "backup_digest_mismatch"
    now = datetime.now(timezone.utc)
    age = max(0.0, (now - manifest.completed_at).total_seconds())
    return {
        "healthy": healthy,
        "reason": reason,
        "age_seconds": age,
        "latest": manifest.model_dump(mode="json"),
        "manifest": manifest_path.name,
    }


def apply_retention(settings: BackupSettings) -> dict[str, int]:
    records = _records(settings.backup_directory)
    keep: set[Path] = set()
    buckets: tuple[tuple[str, int], ...] = (
        ("daily", settings.daily_generations),
        ("weekly", settings.weekly_generations),
        ("monthly", settings.monthly_generations),
    )
    keep.update(path for path, _ in records[: settings.recent_generations])
    for kind, limit in buckets:
        seen: set[str] = set()
        for path, manifest in records:
            key = _bucket(manifest.completed_at, kind)
            if key in seen:
                continue
            seen.add(key)
            if len(seen) <= limit:
                keep.add(path)
    removed = 0
    for path, manifest in records:
        if path in keep:
            continue
        dump = settings.backup_directory / manifest.filename
        dump.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        removed += 1
    return {"retained": len(keep), "removed": removed}


def restore_drill(settings: BackupSettings) -> dict[str, object]:
    inspection = inspect_latest(settings, verify_digest=True)
    if not inspection["healthy"]:
        raise RuntimeError(f"Latest backup is not restorable: {inspection['reason']}.")
    manifest = BackupManifest.model_validate(inspection["latest"])
    dump = settings.backup_directory / manifest.filename
    container = f"swarm-restore-drill-{uuid.uuid4().hex[:12]}"
    started = datetime.now(timezone.utc)
    try:
        _run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--network",
                "none",
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                settings.restore_image,
            ]
        )
        _wait_for_postgres(container)
        _run(["docker", "exec", container, "createdb", "-U", "postgres", "restore_check"])
        with dump.open("rb") as source:
            _run(
                [
                    "docker",
                    "exec",
                    "-i",
                    container,
                    "pg_restore",
                    "--no-owner",
                    "--no-privileges",
                    "-U",
                    "postgres",
                    "-d",
                    "restore_check",
                ],
                stdin=source,
            )
        marker = _container_query(
            container, "select version_num from alembic_version;"
        )
        table_count = int(
            _container_query(
                container,
                "select count(*) from information_schema.tables "
                "where table_schema = 'public';",
            )
        )
        if marker != manifest.migration_marker or table_count < 3:
            raise RuntimeError("Restored database failed structural verification.")
        completed = datetime.now(timezone.utc)
        dossier = {
            "schema_version": "control-plane-restore-drill-v1.0.0",
            "backup_id": manifest.backup_id,
            "backup_sha256": manifest.sha256,
            "migration_marker": marker,
            "public_table_count": table_count,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "rpo_seconds": max(0.0, (started - manifest.completed_at).total_seconds()),
            "rto_seconds": max(0.0, (completed - started).total_seconds()),
            "network_isolated": True,
            "production_database_touched": False,
            "success": True,
        }
        path = settings.backup_directory / "latest-restore-drill.json"
        _write_json(path, dossier)
        return dossier
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )


def _records(directory: Path) -> list[tuple[Path, BackupManifest]]:
    records = []
    for path in directory.glob("*.manifest.json"):
        try:
            manifest = BackupManifest.model_validate_json(path.read_text())
            if Path(manifest.filename).name != manifest.filename:
                continue
            records.append((path, manifest))
        except (OSError, ValueError):
            continue
    return sorted(records, key=lambda item: item[1].completed_at, reverse=True)


def _bucket(value: datetime, kind: str) -> str:
    if kind == "daily":
        return value.strftime("%Y-%m-%d")
    if kind == "weekly":
        year, week, _ = value.isocalendar()
        return f"{year}-W{week:02d}"
    return value.strftime("%Y-%m")


def _database_exec(settings: BackupSettings) -> list[str]:
    return ["docker", "exec", "-i", settings.database_container]


def _run(
    command: list[str],
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | int | None = None,
    capture: bool = False,
) -> str:
    completed = subprocess.run(
        command,
        stdin=stdin,
        stdout=subprocess.PIPE if capture else stdout,
        stderr=subprocess.PIPE,
        check=False,
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
    )
    if completed.returncode != 0:
        detail = _safe_error_detail(completed.stderr)
        raise RuntimeError(
            "Backup subprocess failed with return code "
            f"{completed.returncode}: {detail}"
        )
    return completed.stdout.decode().strip() if capture and completed.stdout else ""


def _safe_error_detail(value: bytes | None) -> str:
    text = (value or b"").decode(errors="replace").strip().splitlines()
    detail = text[-1][-1000:] if text else "no diagnostic output"
    detail = re.sub(
        r"(?i)(password|token|secret|authorization)(\s*[=:]\s*)\S+",
        r"\1\2[REDACTED]",
        detail,
    )
    detail = re.sub(r"(://[^:/\s]+:)[^@\s]+@", r"\1[REDACTED]@", detail)
    return detail


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(path: Path, manifest: BackupManifest) -> None:
    _write_json(path, manifest.model_dump(mode="json"))


def _write_json(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    with temporary.open("rb") as source:
        os.fsync(source.fileno())
    os.replace(temporary, path)


def _wait_for_postgres(container: str) -> None:
    for _ in range(60):
        completed = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("Disposable restore database did not become ready.")


def _container_query(container: str, query: str) -> str:
    return _run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "restore_check",
            "--tuples-only",
            "--no-align",
            "--command",
            query,
        ],
        capture=True,
    ).strip()


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("A control-plane backup is already running.") from exc
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description="Verified control-plane backup utility")
    parser.add_argument(
        "command", choices=("create", "inspect", "verify", "retain", "restore-drill")
    )
    args = parser.parse_args()
    settings = BackupSettings()
    if args.command == "create":
        result = create_backup(settings).model_dump(mode="json")
    elif args.command == "inspect":
        result = inspect_latest(settings)
    elif args.command == "verify":
        result = inspect_latest(settings, verify_digest=True)
        if not result["healthy"]:
            raise RuntimeError(str(result["reason"]))
    elif args.command == "retain":
        result = apply_retention(settings)
    else:
        result = restore_drill(settings)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
