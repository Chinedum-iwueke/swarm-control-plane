from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from swarm_worker import control_plane_backup as backup


def settings(tmp_path: Path) -> backup.BackupSettings:
    runtime = tmp_path / "runtime"
    directory = runtime / "backups"
    directory.mkdir(parents=True)
    (runtime / "compose.yaml").write_text("services: {}\n")
    return backup.BackupSettings(
        runtime=runtime,
        backup_directory=directory,
        lock_path=tmp_path / "backup.lock",
        min_free_bytes=1_048_576,
    )


def test_backup_is_verified_and_atomically_manifested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings(tmp_path)

    def run(command, *, stdin=None, stdout=None, capture=False):
        if "pg_dump" in command:
            stdout.write(b"verified custom dump")
        return "b6f2a9c41d80" if capture else ""

    monkeypatch.setattr(backup, "_run", run)
    manifest = backup.create_backup(configured)
    dump = configured.backup_directory / manifest.filename
    record = dump.with_suffix(".manifest.json")
    assert dump.read_bytes() == b"verified custom dump"
    assert manifest.sha256 == hashlib.sha256(dump.read_bytes()).hexdigest()
    assert manifest.migration_marker == "b6f2a9c41d80"
    assert record.stat().st_mode & 0o777 == 0o640
    assert not list(configured.backup_directory.glob("*.partial"))
    assert backup.inspect_latest(configured, verify_digest=True)["healthy"] is True


def test_backup_targets_only_the_configured_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings(tmp_path)
    commands = []

    def run(command, *, stdin=None, stdout=None, capture=False):
        commands.append(command)
        if "pg_dump" in command:
            stdout.write(b"verified custom dump")
        return "head" if capture else ""

    monkeypatch.setattr(backup, "_run", run)
    backup.create_backup(configured)
    assert commands
    assert all(command[:4] == ["docker", "exec", "-i", "swarm-postgres"] for command in commands)
    assert all("compose" not in command for command in commands)


def test_failed_dump_never_publishes_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("simulated interrupted dump")

    monkeypatch.setattr(backup, "_run", fail)
    with pytest.raises(RuntimeError, match="interrupted"):
        backup.create_backup(configured)
    assert not list(configured.backup_directory.iterdir())


def test_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    _generation(configured.backup_directory, datetime.now(UTC), "original")
    dump = next(configured.backup_directory.glob("*.dump"))
    dump.write_text("tampered")
    result = backup.inspect_latest(configured, verify_digest=True)
    assert result["healthy"] is False
    assert result["reason"] == "backup_file_mismatch"


def test_retention_keeps_daily_weekly_monthly_and_latest(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    for offset in range(70):
        _generation(configured.backup_directory, now - timedelta(days=offset), str(offset))
    result = backup.apply_retention(configured)
    assert result["retained"] >= 7
    assert result["retained"] <= 18
    assert len(list(configured.backup_directory.glob("*.dump"))) == result["retained"]


def test_retention_always_keeps_two_latest_same_day_generations(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    _generation(configured.backup_directory, now, "newest")
    _generation(configured.backup_directory, now - timedelta(minutes=5), "previous")
    result = backup.apply_retention(configured)
    assert result == {"retained": 2, "removed": 0}


def test_overlap_lock_fails_closed(tmp_path: Path) -> None:
    lock = tmp_path / "backup.lock"
    with backup._exclusive_lock(lock), pytest.raises(
        RuntimeError, match="already running"
    ), backup._exclusive_lock(lock):
        pass


def test_restore_drill_is_digest_bound_and_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings(tmp_path)
    completed = datetime.now(UTC) - timedelta(minutes=5)
    _generation(configured.backup_directory, completed, "restore")
    commands: list[list[str]] = []

    def run(command, **kwargs):
        commands.append(command)
        if "select version_num" in " ".join(command):
            return "head"
        if "information_schema.tables" in " ".join(command):
            return "42"
        return ""

    monkeypatch.setattr(backup, "_run", run)
    monkeypatch.setattr(backup, "_wait_for_postgres", lambda container: None)
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: None)
    dossier = backup.restore_drill(configured)
    docker_run = next(command for command in commands if command[:2] == ["docker", "run"])
    assert docker_run[docker_run.index("--network") + 1] == "none"
    assert dossier["migration_marker"] == "head"
    assert dossier["public_table_count"] == 42
    assert dossier["production_database_touched"] is False
    assert (configured.backup_directory / "latest-restore-drill.json").is_file()


def test_subprocess_diagnostic_is_bounded_and_redacted() -> None:
    detail = backup._safe_error_detail(
        b"old line\npassword=do-not-print https://user:private@example.test\n"
    )
    assert "do-not-print" not in detail
    assert "private" not in detail
    assert "[REDACTED]" in detail
    assert len(detail) <= 1000


def _generation(directory: Path, completed: datetime, suffix: str) -> None:
    filename = f"swarm_control_{completed:%Y%m%dT%H%M%SZ}_{suffix}.dump"
    content = f"dump-{suffix}".encode()
    (directory / filename).write_bytes(content)
    manifest = backup.BackupManifest(
        backup_id=f"backup-{suffix}",
        database="swarm_control",
        filename=filename,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        migration_marker="head",
        started_at=completed - timedelta(seconds=1),
        completed_at=completed,
        integrity_verified=True,
        host="vm2",
    )
    (directory / filename.replace(".dump", ".manifest.json")).write_text(
        json.dumps(manifest.model_dump(mode="json"))
    )
