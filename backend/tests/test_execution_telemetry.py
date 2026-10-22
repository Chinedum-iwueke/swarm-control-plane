from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.execution_telemetry import router
from app.schemas.execution_telemetry import (
    ExecutionTelemetryReplayCreate,
    ExecutionTelemetrySchemaCreate,
)
from app.services.execution_telemetry import (
    ExecutionTelemetryConflict,
    digest,
    normalize_event_history,
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
        "/v1/execution/events",
    }


def telemetry_event(sequence, kind, payload, **overrides):
    core = {
        "schema_version": "exec011-venue-telemetry-v1.0.0",
        "event_id": f"event-{sequence}",
        "venue": "bybit",
        "environment": "demo",
        "account_pseudonym": "acct-demo-7",
        "instrument_id": "bybit:linear:BTCUSDT",
        "stream": "private-orders",
        "kind": kind,
        "exchange_time": f"2026-09-12T12:00:{sequence:02d}+00:00",
        "source_time": f"2026-09-12T12:00:{sequence:02d}.010000+00:00",
        "receive_time": f"2026-09-12T12:00:{sequence:02d}.020000+00:00",
        "sequence": sequence,
        "cursor": str(sequence),
        "raw_reference_digest": f"{sequence:x}" * 64,
        "normalization_version": "1.0.0",
        "correction_of": None,
        "reconciliation_id": None,
        "payload": payload,
        "payload_digest": digest(payload),
    }
    core.update(overrides)
    return {**core, "event_digest": digest(core)}


def replay_and_receipt(events):
    view = projection()
    view["event_history"] = events
    view_core = {
        key: value for key, value in view.items() if key != "projection_digest"
    }
    view["projection_digest"] = digest(view_core)
    replay = SimpleNamespace(
        id=uuid4(),
        receipt_digest="d" * 64,
        projection_digest=view["projection_digest"],
        venue="bybit",
        environment="demo",
        account_pseudonym="acct-demo-7",
        projection=view,
    )
    receipt = SimpleNamespace(
        id=uuid4(),
        receipt_digest="d" * 64,
        receipt={"result": {"projection_digest": view["projection_digest"]}},
    )
    return replay, receipt


def test_normalized_history_is_deterministic_and_semantically_distinct():
    command = telemetry_event(
        1,
        "intent",
        {
            "intent_id": "corr-1",
            "client_order_id": "client-1",
            "action": "submit",
        },
    )
    acknowledgement = telemetry_event(
        2,
        "order",
        {"client_order_id": "client-1", "order_id": "venue-1", "status": "new"},
    )
    partial_fill = telemetry_event(
        3,
        "fill",
        {
            "execution_id": "exec-1",
            "client_order_id": "client-1",
            "order_id": "venue-1",
            "quantity": "0.25",
            "price": "100",
            "fill_status": "partial",
        },
    )
    replay, receipt = replay_and_receipt(
        [partial_fill, acknowledgement, command, acknowledgement]
    )
    first, coverage = normalize_event_history(replay, receipt)
    second, _ = normalize_event_history(replay, receipt)
    assert first == second
    assert [item["event_type"] for item in first] == [
        "oms_command",
        "venue_acknowledgement",
        "fill",
    ]
    assert first[0]["event_type"] != first[1]["event_type"]
    assert first[0]["event_type"] != first[2]["event_type"]
    assert first[2]["payload"]["fill_status"] == "partial"
    assert coverage["duplicates_suppressed"] == 1
    assert all(item["evidence"]["receipt_path"] for item in first)


def test_connectivity_kill_stale_and_reconciliation_timeline():
    events = [
        telemetry_event(1, "incident", {"category": "stale_feed"}),
        telemetry_event(2, "incident", {"category": "private_stream_reconnect"}),
        telemetry_event(3, "incident", {"category": "runtime_kill"}),
        telemetry_event(
            4,
            "reconciliation",
            {
                "positions": {"bybit:linear:BTCUSDT": "0"},
                "cash": {"USDT": "100"},
            },
            reconciliation_id="recon-1",
        ),
    ]
    replay, receipt = replay_and_receipt(list(reversed(events)))
    normalized, _ = normalize_event_history(replay, receipt)
    assert [item["event_type"] for item in normalized] == [
        "connectivity",
        "connectivity",
        "kill",
        "reconciliation",
    ]
    assert normalized[-1]["reconciliation_id"] == "recon-1"


def test_legacy_summary_is_disclosed_without_synthetic_events():
    replay, receipt = replay_and_receipt([])
    replay.projection.pop("event_history")
    core = {
        key: value
        for key, value in replay.projection.items()
        if key != "projection_digest"
    }
    replay.projection["projection_digest"] = digest(core)
    replay.projection_digest = replay.projection["projection_digest"]
    receipt.receipt["result"]["projection_digest"] = replay.projection_digest
    events, coverage = normalize_event_history(replay, receipt)
    assert events == []
    assert coverage["coverage"] == "legacy_summary_only"
    assert "not event envelopes" in coverage["reason"]


def test_event_digest_and_identity_collisions_fail_closed():
    event = telemetry_event(1, "fill", {"execution_id": "exec-1"})
    tampered = {**event, "payload": {"execution_id": "exec-2"}}
    replay, receipt = replay_and_receipt([tampered])
    with pytest.raises(ExecutionTelemetryConflict, match="payload digest"):
        normalize_event_history(replay, receipt)
    collision = telemetry_event(1, "fill", {"execution_id": "exec-2"})
    replay, receipt = replay_and_receipt([event, collision])
    with pytest.raises(ExecutionTelemetryConflict, match="reused"):
        normalize_event_history(replay, receipt)


def test_event_type_override_and_clock_causality_fail_closed():
    relabeled = telemetry_event(
        1,
        "fill",
        {"execution_id": "exec-1", "event_type": "oms_command"},
    )
    replay, receipt = replay_and_receipt([relabeled])
    with pytest.raises(ExecutionTelemetryConflict, match="incompatible"):
        normalize_event_history(replay, receipt)
    invalid_clock = telemetry_event(
        1,
        "fill",
        {"execution_id": "exec-1"},
        source_time="2026-09-12T12:00:02+00:00",
        receive_time="2026-09-12T12:00:01+00:00",
    )
    replay, receipt = replay_and_receipt([invalid_clock])
    with pytest.raises(ExecutionTelemetryConflict, match="causal ordering"):
        normalize_event_history(replay, receipt)
