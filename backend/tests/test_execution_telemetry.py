from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.api.routes.execution_telemetry import router
from app.schemas.execution_telemetry import (
    ExecutionTelemetryReplayCreate,
    ExecutionTelemetrySchemaCreate,
)
from app.services.execution_telemetry import (
    ExecutionTelemetryConflict,
    digest,
    register_replay,
    register_schema,
)


def specification():
    return {"schema_version": "exec011-venue-telemetry-v1.0.0", "secrets": "forbidden"}


def schema_payload(**overrides):
    values = {
        "name": "canonical-venue-telemetry",
        "version": "1.0.0",
        "producer": "bt.institutional.venue_telemetry.venue_telemetry_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec011-pilot",
    }
    values.update(overrides)
    return ExecutionTelemetrySchemaCreate.model_validate(values)


def projection():
    value = {
        "schema_version": "exec011-venue-telemetry-v1.0.0",
        "known_at": "2026-09-12T12:00:00+00:00",
        "status": "current",
        "stale": False,
        "event_count": 3,
        "active_event_count": 3,
        "duplicate_event_count": 0,
        "sequence_gaps": [],
        "reconciliation_discrepancies": [],
        "orders": [],
        "fills": [],
        "positions": [],
        "cash": [{"asset": "USDT", "balance": "100"}],
        "margins": [],
        "fees": "0",
        "funding": "0",
        "incidents": [],
        "trade_episodes": [],
        "event_head_digest": "c" * 64,
    }
    return {**value, "projection_digest": digest(value)}


def replay_payload(**overrides):
    view = projection()
    values = {
        "receipt_digest": "d" * 64,
        "projection_digest": view["projection_digest"],
        "schema_digest": digest(specification()),
        "venue": "bybit",
        "environment": "demo",
        "account_pseudonym": "acct-demo-7",
        "observed_at": datetime(2026, 9, 12, 12, tzinfo=UTC),
        "status": "current",
        "projection": view,
        "registered_by": "exec011-pilot",
    }
    values.update(overrides)
    return ExecutionTelemetryReplayCreate.model_validate(values)


def bound_receipt(payload):
    return SimpleNamespace(
        receipt={
            "result": {
                "projection_digest": payload.projection_digest,
                "telemetry_schema_digest": payload.schema_digest,
                "venue": payload.venue,
                "environment": payload.environment,
                "account_pseudonym": payload.account_pseudonym,
            }
        }
    )


def test_schema_registration_is_immutable_and_idempotent():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_schema(db, schema_payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_schema(replay, schema_payload()) is record
    with pytest.raises(ExecutionTelemetryConflict, match="digest"):
        register_schema(MagicMock(), schema_payload(specification_digest="0" * 64))


def test_replay_requires_active_schema_exact_receipt_and_matching_digest():
    payload = replay_payload()
    db = MagicMock()
    db.scalar.side_effect = [object(), bound_receipt(payload), None]
    record = register_replay(db, payload)
    assert record.environment == "demo"
    assert record.projection["cash"][0]["asset"] == "USDT"
    missing = MagicMock()
    missing.scalar.return_value = None
    with pytest.raises(ExecutionTelemetryConflict, match="schema is not active"):
        register_replay(missing, payload)


def test_replay_rejects_secret_and_raw_payload_fields():
    view = projection()
    view["api_key"] = "must-not-persist"
    core = {key: value for key, value in view.items() if key != "projection_digest"}
    view["projection_digest"] = digest(core)
    payload = replay_payload(
        projection=view, projection_digest=view["projection_digest"]
    )
    db = MagicMock()
    db.scalar.side_effect = [object(), bound_receipt(payload), None]
    with pytest.raises(ExecutionTelemetryConflict, match="forbidden"):
        register_replay(db, payload)


def test_routes_are_orchestrator_protected_and_complete():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/execution/telemetry-schemas",
        "/v1/execution/replays",
        "/v1/execution/replays/{replay_id}",
        "/v1/execution/overview",
    }
