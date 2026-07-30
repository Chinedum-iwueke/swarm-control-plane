import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml

from swarm_worker.infrastructure.postgres_deployment import (
    PostgresDeploymentError,
    PostgresDeploymentManager,
)


class ComposeLoader(yaml.SafeLoader):
    pass


ComposeLoader.add_constructor("!reset", lambda loader, node: [])


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
        "100.112.117.59:6432:5432"
    ]
    assert compose["services"]["postgres"]["image"].endswith(
        "@sha256:92620daddcd947f8d5ab5ba66e848702fe443d87fed30c4cea8e389fd78dfc55"
    )
    assert compose["services"]["pgbouncer"]["image"].endswith(
        "@sha256:3db3d7223e93af52b4116f642951a1a5fa44702a88c2a59cf7562cac19320c9e"
    )
    override = yaml.load(
        (root / "schema/worker-network.override.yaml").read_text(),
        Loader=ComposeLoader,
    )
    assert override["networks"]["invariance-postgres"] == {
        "external": True,
        "name": "invariance-postgres_default",
    }
    assert override["services"]["analysis-worker"]["env_file"] == []
    rendered = str(result)
    environment = (root / ".env.postgres").read_text()
    for line in environment.splitlines():
        if "PASSWORD=" in line:
            assert line.split("=", 1)[1] not in rendered


def test_stage_supports_isolated_rehearsal_binding(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    PostgresDeploymentManager(
        root,
        postgres_uid=os.geteuid(),
        postgres_gid=os.getegid(),
        pgbouncer_bind_address="127.0.0.1",
    ).stage()

    compose = yaml.safe_load((root / "compose.yaml").read_text())
    assert compose["services"]["pgbouncer"]["ports"] == [
        "127.0.0.1:6432:5432"
    ]
    assert "100.112.117.59" not in (root / "compose.yaml").read_text()


def test_stage_is_idempotent_only_for_untampered_metadata(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    first = manager(root).stage()
    second = manager(root).stage()
    assert first["metadata_sha256"] == second["metadata_sha256"]
    assert second["reused"] is True

    (root / "compose.yaml").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PostgresDeploymentError, match="digest"):
        manager(root).stage()


def test_staged_check_is_read_only_and_rejects_tampering(tmp_path: Path) -> None:
    root = tmp_path / "postgres"
    manager(root).stage()
    metadata_before = (root / "metadata.json").read_bytes()

    assert manager(root).is_staged() is True
    assert (root / "metadata.json").read_bytes() == metadata_before

    (root / "compose.yaml").write_text("tampered\n", encoding="utf-8")
    assert manager(root).is_staged() is False


def test_stage_upgrades_static_template_without_rotating_secrets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "postgres"
    manager(root).stage()
    environment = (root / ".env.postgres").read_bytes()
    old_compose = "name: invariance-postgres\nservices: {}\n"
    (root / "compose.yaml").write_text(old_compose, encoding="utf-8")
    metadata_path = root / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["deployment_version"] = "1.0.0"
    metadata["files"]["compose.yaml"] = hashlib.sha256(
        old_compose.encode()
    ).hexdigest()
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = manager(root).stage()

    upgraded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert result["reused"] is True
    assert upgraded["deployment_version"] == "1.3.0"
    assert (root / ".env.postgres").read_bytes() == environment
    assert "invariance_owner 172.16.0.0/12" in (
        root / "conf/pg_hba.conf"
    ).read_text(encoding="utf-8")
    assert "edoburu/pgbouncer:v1.24.1-p1@sha256:" in (
        root / "compose.yaml"
    ).read_text(encoding="utf-8")


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
        path = root / name
        path.mkdir()
        if name in {"archive", "data", "logs"}:
            path.chmod(0o750)

    candidate = manager(root)
    assert candidate.is_preprovisioned() is True

    result = candidate.stage()

    assert result["staged"] is True
    assert (root / "metadata.json").is_file()
