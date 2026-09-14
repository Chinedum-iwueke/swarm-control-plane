from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.models.fleet import FleetIncident, FleetIncidentEvent
from app.schemas.fleet import FleetMetrics, MachineObservationCreate, ServiceHealth
from app.services.agents import calculate_presence
from app.services.fleet import (
    STALE_AFTER,
    _advance,
    evaluate_observation,
    resolve_machine_presence,
)
from pydantic import ValidationError


class FakeDB:
    def __init__(self):
        self.incident = None
        self.events = []

    def scalar(self, statement):
        return self.incident

    def add(self, value):
        if isinstance(value, FleetIncident):
            self.incident = value
        elif isinstance(value, FleetIncidentEvent):
            self.events.append(value)

    def flush(self):
        return None


def test_single_spike_does_not_notify_and_sustained_signal_notifies_once() -> None:
    db = FakeDB()
    now = datetime.now(UTC)
    with patch("app.services.fleet._notify") as notify:
        _advance(
            db, "vm1-developer", "cpu_saturation", True, "warning", {"value": 99}, now
        )
        assert db.incident.state == "pending"
        notify.assert_not_called()
        _advance(
            db, "vm1-developer", "cpu_saturation", True, "warning", {"value": 98}, now
        )
        _advance(
            db, "vm1-developer", "cpu_saturation", True, "warning", {"value": 97}, now
        )
        _advance(
            db, "vm1-developer", "cpu_saturation", True, "warning", {"value": 96}, now
        )
    assert db.incident.state == "warning"
    assert notify.call_count == 1


def test_recovery_requires_hysteresis_and_notifies_once() -> None:
    db = FakeDB()
    now = datetime.now(UTC)
    with patch("app.services.fleet._notify") as notify:
        for _ in range(3):
            _advance(
                db,
                "vm2-deployment",
                "memory_pressure",
                True,
                "critical",
                {"value": 5},
                now,
            )
        for _ in range(2):
            _advance(
                db,
                "vm2-deployment",
                "memory_pressure",
                False,
                "critical",
                {"value": 40},
                now,
            )
        assert db.incident.state == "critical"
        _advance(
            db,
            "vm2-deployment",
            "memory_pressure",
            False,
            "critical",
            {"value": 40},
            now,
        )
    assert db.incident.state == "recovered"
    assert notify.call_count == 2


def test_observation_contract_rejects_unknown_fields_and_duplicate_services() -> None:
    metrics = FleetMetrics(
        cpu_utilization_percent=1,
        load_per_core=0.1,
        memory_available_percent=80,
        swap_used_percent=0,
        swap_in_bytes_delta=0,
        swap_out_bytes_delta=0,
        disk_used_percent=10,
        inode_used_percent=2,
        cpu_pressure_avg10=0,
        io_pressure_avg10=0,
        memory_pressure_avg10=0,
        uptime_seconds=100,
        oom_kills_delta=0,
    )
    service = ServiceHealth(name="api.service", status="active")
    with pytest.raises(ValidationError):
        MachineObservationCreate.model_validate(
            {
                "schema_version": "fleet-observation-v1.0.0",
                "sample_id": "sample-123",
                "machine": "vm1-developer",
                "observed_at": datetime.now(UTC),
                "metrics": metrics.model_dump(),
                "services": [service.model_dump(), service.model_dump()],
                "command": "env",
            }
        )


def test_backup_freshness_warns_before_deadline_and_recovers() -> None:
    metrics = {
        "cpu_utilization_percent": 1,
        "load_per_core": 0.1,
        "memory_available_percent": 80,
        "swap_used_percent": 0,
        "swap_in_bytes_delta": 0,
        "swap_out_bytes_delta": 0,
        "disk_used_percent": 10,
        "inode_used_percent": 2,
        "cpu_pressure_avg10": 0,
        "io_pressure_avg10": 0,
        "memory_pressure_avg10": 0,
        "uptime_seconds": 100,
        "oom_kills_delta": 0,
        "control_plane_backup_age_seconds": 550_000,
        "control_plane_backup_verified": True,
        "control_plane_backup_failed": False,
    }
    observation = SimpleNamespace(
        machine="vm2-deployment",
        metrics=metrics,
        service_health={},
        observed_at=datetime.now(UTC),
    )
    with patch("app.services.fleet._advance") as advance:
        evaluate_observation(FakeDB(), observation)
    backup_call = next(
        call for call in advance.call_args_list if call.args[2] == "control_plane_backup"
    )
    assert backup_call.args[3] is True
    assert backup_call.args[4] == "warning"
    assert backup_call.args[5]["critical_after_seconds"] == 604_800


def test_machine_presence_evidence_thresholds_are_aligned() -> None:
    assert STALE_AFTER.total_seconds() == 90
    now = datetime.now(UTC)
    agent = SimpleNamespace(is_enabled=True, last_heartbeat_at=now)
    assert calculate_presence(agent) == "online"
    assert resolve_machine_presence(now, ["offline"], now) == ("online", "current")
    assert resolve_machine_presence(now - timedelta(days=1), ["online"], now) == (
        "online",
        "stale",
    )
    assert resolve_machine_presence(None, ["offline"], now) == (
        "offline",
        "missing",
    )
