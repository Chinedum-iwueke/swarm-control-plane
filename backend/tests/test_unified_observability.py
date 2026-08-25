from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.models.observability import ServiceSLOState
from app.services.observability import _route_state, _service_rows, sanitized


class RouteDB:
    def __init__(self):
        self.values = []

    def scalar(self, _statement):
        return None

    def add(self, value):
        self.values.append(value)

    def flush(self):
        return None


def entry(**slo):
    return {
        "service_key": "control-plane-api",
        "owner": "platform-operations",
        "intended_machines": ["vm2-deployment"],
        "slo": slo,
    }


def test_single_health_sample_is_current_evidence_not_historical_uptime() -> None:
    now = datetime.now(UTC)
    rows = _service_rows(
        entry(availability_percent=99.0),
        {
            "service_key": "control-plane-api",
            "status": "healthy",
            "observed_at": now.isoformat(),
        },
        {},
        now,
    )

    availability = next(item for item in rows if item["indicator"] == "availability")
    assert availability["status"] == "healthy"
    assert availability["objective"]["window"] == "current_evidence"
    assert availability["measurement"] == {
        "observed_percent": 100.0,
        "sample_count": 1,
    }


def test_missing_restore_measurement_is_unknown_not_green() -> None:
    rows = _service_rows(entry(rto_seconds=1800), None, {}, datetime.now(UTC))
    assert rows[0]["indicator"] == "recovery_time"
    assert rows[0]["status"] == "unknown"
    assert rows[0]["measurement"]["measured_seconds"] is None


def test_secret_shaped_evidence_is_redacted_and_bounded() -> None:
    result = sanitized(
        {
            "token": "must-not-escape",
            "nested": {"Authorization": "Bearer must-not-escape"},
            "safe": "x" * 1_000,
            "message": "upstream failed token=must-not-escape",
        }
    )
    assert result["token"] == "[REDACTED]"
    assert result["nested"]["Authorization"] == "[REDACTED]"
    assert len(result["safe"]) == 500
    assert "must-not-escape" not in result["message"]


def test_alert_requires_three_consecutive_breaches_and_routes_once() -> None:
    now = datetime.now(UTC)
    state = ServiceSLOState(
        id=uuid4(),
        service_key="control-plane-api",
        indicator="availability",
        owner="platform-operations",
        status="breached",
        objective={},
        measurement={},
        evidence={},
        consecutive_breaches=2,
        consecutive_healthy=0,
        evaluated_at=now,
        record_digest="0" * 64,
    )
    db = RouteDB()
    with (
        patch("app.services.observability._notify") as notify,
        patch("app.services.observability._alert_event") as event,
    ):
        _route_state(db, state, now)
        assert not db.values
        state.consecutive_breaches = 3
        _route_state(db, state, now)
    assert len(db.values) == 1
    assert db.values[0].route == "founder-outbox"
    notify.assert_called_once()
    event.assert_called_once()


def test_capacity_breach_is_attributed_to_catalog_service_and_machine() -> None:
    now = datetime.now(UTC)
    machine = SimpleNamespace(
        machine="vm2-deployment",
        observed_at=now,
        metrics={"memory_available_percent": 8, "disk_used_percent": 70},
    )
    rows = _service_rows(entry(), None, {"vm2-deployment": machine}, now)
    assert rows[0]["indicator"] == "capacity"
    assert rows[0]["status"] == "breached"
    assert rows[0]["evidence"]["machine"] == "vm2-deployment"
