import os
from pathlib import Path

import pytest
import yaml

from swarm_worker.infrastructure.postgres_deployment import (
    PostgresDeploymentError,
    PostgresDeploymentManager,
)


def manager(root: Path) -> PostgresDeploymentManager:
    return PostgresDeploymentManager(
        root,
        postgres_uid=os.geteuid(),
        postgres_gid=os.getegid(),
    )


def test_stage_creates_private_digest_bound_layout(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    result = manager(root).stage()

    assert result["staged"] is True
    assert result["public_access"] is False
    assert result["network_mode"] == "tailscale-private"
    assert (root / ".env.postgres").stat().st_mode & 0o777 == 0o600
    assert (root / "metadata.json").stat().st_mode & 0o777 == 0o600
    assert (root / "init/001-invariance.sh").stat().st_mode & 0o777 == 0o755
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    assert compose["services"]["postgres"]["ports"] == ["127.0.0.1:5432:5432"]
    assert compose["services"]["pgbouncer"]["ports"] == [
        "100.112.117.59:6432:6432"
    ]
    override = yaml.safe_load(
        (root / "schema/worker-network.override.yaml").read_text()
    )
    assert override["networks"]["invariance-postgres"] == {
        "external": True,
        "name": "invariance-postgres_default",
    }
    rendered = str(result)
    environment = (root / ".env.postgres").read_text()
    for line in environment.splitlines():
        if "PASSWORD=" in line:
            assert line.split("=", 1)[1] not in rendered


def test_stage_is_idempotent_only_for_untampered_metadata(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    first = manager(root).stage()
    second = manager(root).stage()
    assert first["metadata_sha256"] == second["metadata_sha256"]
    assert second["reused"] is True

    (root / "compose.yaml").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PostgresDeploymentError, match="digest"):
        manager(root).stage()


def test_stage_refuses_unknown_non_empty_root(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    root.mkdir()
    (root / "unknown").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(PostgresDeploymentError, match="metadata"):
        manager(root).stage()


def test_stage_accepts_exact_empty_preprovisioned_layout(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    root.mkdir()
    for name in (
        "archive",
        "backups",
        "bin",
        "certs",
        "conf",
        "data",
        "init",
        "logs",
        "pgbouncer",
        "schema",
    ):
        (root / name).mkdir()

    candidate = manager(root)
    assert candidate.is_preprovisioned() is True

    result = candidate.stage()

    assert result["staged"] is True
    assert (root / "metadata.json").is_file()
