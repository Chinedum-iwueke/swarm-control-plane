from datetime import datetime, timezone

from hermes_mission_control.freshness import build_snapshot_provenance

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _snapshot(**overrides):
    snapshot = {
        "health": {"status": "ok"},
        "tasks": [{"updated_at": "2026-10-22T11:59:30Z"}],
        "agents": [{"last_heartbeat_at": "2026-10-22T11:59:30Z"}],
        "fleet_health": {"generated_at": "2026-10-22T11:59:30Z"},
        "observability": {"generated_at": "2026-10-22T11:59:30Z"},
        "execution_telemetry": {"generated_at": "2026-10-22T11:59:30Z"},
        "backtest_activity": {"generated_at": "2026-10-22T11:59:30Z"},
        "research_utilization": {"generated_at": "2026-10-22T11:59:30Z"},
        "alpha_discovery": {"generated_at": "2026-10-22T11:59:30Z"},
    }
    snapshot.update(overrides)
    return snapshot


def test_missing_source_time_fails_closed_to_unknown_and_partial_snapshot() -> None:
    provenance = build_snapshot_provenance(_snapshot(), now=NOW)

    assert provenance.sources["health"].freshness == "unknown"
    assert provenance.sources["health"].reason == "source_timestamp_missing"
    assert provenance.freshness == "partial"


def test_current_stale_future_and_unavailable_sources_are_classified() -> None:
    provenance = build_snapshot_provenance(
        _snapshot(
            health={"generated_at": "2026-10-22T11:59:30Z"},
            tasks=[{"updated_at": "2026-10-22T11:55:00Z"}],
            agents=[{"last_heartbeat_at": "2026-10-22T12:01:00Z"}],
            execution_telemetry={"unavailable": True},
        ),
        now=NOW,
    )

    assert provenance.sources["health"].freshness == "current"
    assert provenance.sources["tasks"].freshness == "stale"
    assert provenance.sources["agents"].freshness == "unknown"
    assert provenance.sources["agents"].reason == "source_timestamp_in_future"
    assert provenance.sources["execution_telemetry"].freshness == "unavailable"
    assert provenance.freshness == "stale"


def test_provenance_has_stable_schema_and_explicit_source_identities() -> None:
    provenance = build_snapshot_provenance(
        _snapshot(health={"generated_at": "2026-10-22T11:59:30Z"}), now=NOW
    )

    assert provenance.schema_version == "mission-control-provenance-v1"
    assert provenance.source_identity == "mission-control/dashboard"
    assert provenance.sources["backtest_activity"].source_identity.endswith(
        "/backtests/activity"
    )
    assert provenance.sources["execution_telemetry"].freshness_threshold_seconds == 300
