import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from swarm_worker.fleet_probe import ProbeSettings, _service, collect, publish


def settings(tmp_path: Path) -> ProbeSettings:
    token = tmp_path / "token"
    token.write_text("swarm_ag_prefix_secret-value", encoding="utf-8")
    return ProbeSettings(
        api_url="http://control-plane.test",
        agent_token_file=token,
        machine="vm1-developer",
        services="one.service,two.service",
        state_path=tmp_path / "state.json",
    )


def test_collect_has_bounded_aggregate_metrics_only(tmp_path: Path) -> None:
    value = collect(settings(tmp_path))
    assert value["machine"] == "vm1-developer"
    assert set(value["metrics"]) == {
        "cpu_utilization_percent",
        "load_per_core",
        "memory_available_percent",
        "swap_used_percent",
        "swap_in_bytes_delta",
        "swap_out_bytes_delta",
        "disk_used_percent",
        "inode_used_percent",
        "cpu_pressure_avg10",
        "io_pressure_avg10",
        "memory_pressure_avg10",
        "uptime_seconds",
        "oom_kills_delta",
    }
    assert "environment" not in json.dumps(value).lower()


def test_service_probe_uses_argument_array_and_controlled_environment() -> None:
    completed = Mock(stdout="active\n", returncode=0)
    with patch("subprocess.run", return_value=completed) as run:
        assert _service("safe.service") == {"name": "safe.service", "status": "active"}
    args, kwargs = run.call_args
    assert args[0] == ["systemctl", "is-active", "safe.service"]
    assert kwargs["env"] == {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"}
    assert "shell" not in kwargs


def test_publish_does_not_put_token_in_payload(tmp_path: Path) -> None:
    probe_settings = settings(tmp_path)
    response = Mock(status=201)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        publish(probe_settings, {"machine": "vm1-developer"})
    request = urlopen.call_args.args[0]
    assert request.headers["Authorization"].startswith("Bearer swarm_ag_")
    assert b"swarm_ag_" not in request.data


def test_backup_metrics_are_reported_only_when_configured(tmp_path: Path) -> None:
    probe_settings = settings(tmp_path)
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    dump = backup_directory / "generation.dump"
    dump.write_bytes(b"verified")
    (backup_directory / "generation.manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "control-plane-backup-v1.0.0",
                "filename": dump.name,
                "byte_size": dump.stat().st_size,
                "completed_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                "integrity_verified": True,
            }
        )
    )
    configured = probe_settings.model_copy(
        update={"backup_directory": backup_directory}
    )
    metrics = collect(configured)["metrics"]
    assert metrics["control_plane_backup_verified"] is True
    assert metrics["control_plane_backup_failed"] is False
    assert 3500 < metrics["control_plane_backup_age_seconds"] < 3700
