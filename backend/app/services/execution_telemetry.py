import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution_telemetry import (
    ExecutionTelemetryReplay,
    ExecutionTelemetrySchemaRegistry,
)
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.schemas.execution_telemetry import (
    ExecutionTelemetryReplayCreate,
    ExecutionTelemetrySchemaCreate,
)


class ExecutionTelemetryConflict(RuntimeError):
    pass


_EXPLICIT_EVENT_TYPES = {
    "signal_decision",
    "risk_decision",
    "oms_command",
    "venue_acknowledgement",
    "amend_command",
    "amend_acknowledgement",
    "cancel_command",
    "cancel_acknowledgement",
    "fill",
    "position",
    "reconciliation",
    "connectivity",
    "kill",
    "cash",
    "fee",
    "funding",
    "margin",
}
_EVENT_TYPES_BY_SOURCE_KIND = {
    "decision": {"signal_decision", "risk_decision"},
    "intent": {"oms_command", "amend_command", "cancel_command"},
    "order": {
        "venue_acknowledgement",
        "amend_acknowledgement",
        "cancel_acknowledgement",
    },
    "fill": {"fill"},
    "position": {"position"},
    "reconciliation": {"reconciliation"},
    "incident": {"connectivity", "kill"},
    "cash": {"cash"},
    "fee": {"fee"},
    "funding": {"funding"},
    "margin": {"margin"},
}


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def _event_type(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    kind = event.get("kind")
    explicit = payload.get("event_type")
    if explicit in _EXPLICIT_EVENT_TYPES:
        if explicit not in _EVENT_TYPES_BY_SOURCE_KIND.get(str(kind), set()):
            raise ExecutionTelemetryConflict(
                f"Venue event type {explicit!r} is incompatible with source kind {kind!r}."
            )
        return explicit
    if kind == "decision":
        domain = str(payload.get("decision_domain") or payload.get("domain") or "")
        return "risk_decision" if domain.lower() == "risk" else "signal_decision"
    if kind == "intent":
        action = str(payload.get("action") or payload.get("command") or "").lower()
        if action == "amend":
            return "amend_command"
        if action == "cancel":
            return "cancel_command"
        return "oms_command"
    if kind == "order":
        # Order-stream records are venue observations. Commands originate from an
        # intent or an explicit command event_type, never inferred from an order.
        action = str(payload.get("action") or "").lower()
        status = str(payload.get("status") or "").lower()
        if action == "amend" or status in {"amended", "replaced"}:
            return "amend_acknowledgement"
        if action == "cancel" or status in {"cancelled", "canceled"}:
            return "cancel_acknowledgement"
        return "venue_acknowledgement"
    if kind == "incident":
        category = str(payload.get("category") or payload.get("incident_type") or "")
        return "kill" if "kill" in category.lower() else "connectivity"
    if kind in {
        "fill",
        "position",
        "reconciliation",
        "cash",
        "fee",
        "funding",
        "margin",
    }:
        return str(kind)
    raise ExecutionTelemetryConflict(f"Unsupported venue event kind: {kind!r}.")


def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _verify_event(event: dict[str, Any]) -> None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ExecutionTelemetryConflict("Venue event payload must be an object.")
    if event.get("payload_digest") != digest(payload):
        raise ExecutionTelemetryConflict("Venue event payload digest does not match.")
    event_digest = event.get("event_digest")
    core = {key: value for key, value in event.items() if key != "event_digest"}
    if event_digest != digest(core):
        raise ExecutionTelemetryConflict("Venue event digest does not match content.")
    for field in ("event_digest", "raw_reference_digest"):
        value = event.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ExecutionTelemetryConflict(
                f"Venue event {field} must be a lowercase SHA-256 digest."
            )
    if isinstance(event.get("sequence"), bool) or not isinstance(
        event.get("sequence"), int
    ):
        raise ExecutionTelemetryConflict("Venue event sequence must be an integer.")
    exchange = _timestamp(event.get("exchange_time"), "exchange_time")
    source = _timestamp(event.get("source_time"), "source_time")
    observed = _timestamp(event.get("receive_time"), "receive_time")
    if exchange > source or source > observed:
        raise ExecutionTelemetryConflict("Venue event clocks violate causal ordering.")
    _assert_sanitized(payload, "event.payload")


def _timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = (
            value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        )
    except (TypeError, ValueError) as exc:
        raise ExecutionTelemetryConflict(
            f"Venue event {field} must be ISO-8601."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionTelemetryConflict(f"Venue event {field} must be timezone-aware.")
    return parsed.astimezone(UTC)


def _event_documents(projection: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    candidate = projection.get("event_history")
    if candidate is None:
        candidate = projection.get("events")
    if candidate is None:
        return [], "legacy_summary_only"
    if not isinstance(candidate, list):
        raise ExecutionTelemetryConflict("Venue event history must be a list.")
    if any(not isinstance(item, dict) for item in candidate):
        raise ExecutionTelemetryConflict("Venue event history entries must be objects.")
    return [dict(item) for item in candidate], "complete"


def _assert_sanitized(value, path="projection") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if (
                normalized
                in {
                    "api_key",
                    "apikey",
                    "secret",
                    "token",
                    "password",
                    "private_key",
                    "signature",
                    "raw_payload",
                }
                or "credential" in normalized
            ):
                raise ExecutionTelemetryConflict(
                    f"Secret or raw venue content is forbidden at {path}.{key}."
                )
            _assert_sanitized(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_sanitized(nested, f"{path}[{index}]")


def register_schema(
    db: Session, payload: ExecutionTelemetrySchemaCreate
) -> ExecutionTelemetrySchemaRegistry:
    if digest(payload.specification) != payload.specification_digest:
        raise ExecutionTelemetryConflict(
            "Execution-telemetry specification digest does not match content."
        )
    existing = db.scalar(
        select(ExecutionTelemetrySchemaRegistry).where(
            ExecutionTelemetrySchemaRegistry.name == payload.name,
            ExecutionTelemetrySchemaRegistry.version == payload.version,
        )
    )
    if existing:
        if existing.specification_digest != payload.specification_digest:
            raise ExecutionTelemetryConflict(
                "Execution-telemetry schema name and version are immutable."
            )
        return existing
    record = ExecutionTelemetrySchemaRegistry(**payload.model_dump())
    db.add(record)
    db.flush()
    return record


def register_replay(
    db: Session, payload: ExecutionTelemetryReplayCreate
) -> ExecutionTelemetryReplay:
    schema = db.scalar(
        select(ExecutionTelemetrySchemaRegistry).where(
            ExecutionTelemetrySchemaRegistry.specification_digest
            == payload.schema_digest,
            ExecutionTelemetrySchemaRegistry.status == "active",
        )
    )
    if schema is None:
        raise ExecutionTelemetryConflict("Execution-telemetry schema is not active.")
    receipt = db.scalar(
        select(QuantitativeProducerReceipt).where(
            QuantitativeProducerReceipt.receipt_digest == payload.receipt_digest,
            QuantitativeProducerReceipt.milestone == "EXEC-011",
        )
    )
    if receipt is None:
        raise ExecutionTelemetryConflict(
            "Exact EXEC-011 producer receipt is not registered."
        )
    result = receipt.receipt.get("result", {})
    if result.get("projection_digest") != payload.projection_digest:
        raise ExecutionTelemetryConflict(
            "Projection digest is not bound by the EXEC-011 receipt."
        )
    if result.get("telemetry_schema_digest") != payload.schema_digest:
        raise ExecutionTelemetryConflict(
            "Schema digest is not bound by the EXEC-011 receipt."
        )
    if any(
        result.get(key) != getattr(payload, key)
        for key in ("venue", "environment", "account_pseudonym")
    ):
        raise ExecutionTelemetryConflict(
            "Venue identity is not bound by the EXEC-011 receipt."
        )
    if (
        digest(
            {
                key: value
                for key, value in payload.projection.items()
                if key != "projection_digest"
            }
        )
        != payload.projection_digest
    ):
        raise ExecutionTelemetryConflict("Projection digest does not match content.")
    _assert_sanitized(payload.projection)
    existing = db.scalar(
        select(ExecutionTelemetryReplay).where(
            ExecutionTelemetryReplay.receipt_digest == payload.receipt_digest
        )
    )
    if existing:
        if existing.projection_digest != payload.projection_digest:
            raise ExecutionTelemetryConflict("Receipt replay is immutable.")
        return existing
    record = ExecutionTelemetryReplay(**payload.model_dump())
    db.add(record)
    db.flush()
    return record


def normalize_event_history(
    replay: ExecutionTelemetryReplay,
    receipt: QuantitativeProducerReceipt,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify and normalize one immutable replay without inventing legacy events."""
    if receipt.receipt_digest != replay.receipt_digest:
        raise ExecutionTelemetryConflict("Replay receipt binding does not match.")
    result = receipt.receipt.get("result") or {}
    if result.get("projection_digest") != replay.projection_digest:
        raise ExecutionTelemetryConflict("Receipt does not bind the replay projection.")
    projection_core = {
        key: value
        for key, value in replay.projection.items()
        if key != "projection_digest"
    }
    if digest(projection_core) != replay.projection_digest:
        raise ExecutionTelemetryConflict(
            "Stored replay projection digest does not match."
        )
    documents, coverage = _event_documents(replay.projection)
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for event in documents:
        _verify_event(event)
        identity = (
            str(event.get("venue")),
            str(event.get("environment")),
            str(event.get("stream")),
            str(event.get("event_id")),
        )
        prior = unique.get(identity)
        if prior is not None:
            if prior["event_digest"] != event["event_digest"]:
                raise ExecutionTelemetryConflict(
                    "Venue event identity was reused with different content."
                )
            duplicate_count += 1
            continue
        if (
            event.get("venue") != replay.venue
            or event.get("environment") != replay.environment
        ):
            raise ExecutionTelemetryConflict(
                "Venue event identity differs from its replay."
            )
        if event.get("account_pseudonym") != replay.account_pseudonym:
            raise ExecutionTelemetryConflict(
                "Venue event account differs from its replay."
            )
        unique[identity] = event
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            _timestamp(item.get("receive_time"), "receive_time"),
            str(item.get("venue")),
            str(item.get("stream")),
            int(item.get("sequence", 0)),
            str(item.get("event_digest")),
        ),
    )
    events: list[dict[str, Any]] = []
    for event in ordered:
        payload = event["payload"]
        events.append(
            {
                "event_id": str(event["event_id"]),
                "event_type": _event_type(event),
                "source_kind": str(event["kind"]),
                "venue": replay.venue,
                "environment": replay.environment,
                "account_pseudonym": replay.account_pseudonym,
                "instrument_id": str(event["instrument_id"]),
                "stream": str(event["stream"]),
                "correlation_id": _first_text(
                    payload, "correlation_id", "intent_id", "decision_id"
                ),
                "client_order_id": _first_text(payload, "client_order_id"),
                "venue_order_id": _first_text(payload, "venue_order_id", "order_id"),
                "execution_id": _first_text(payload, "execution_id", "exec_id"),
                "exchange_time": _timestamp(event["exchange_time"], "exchange_time"),
                "observed_time": _timestamp(event["receive_time"], "receive_time"),
                "sequence": int(event["sequence"]),
                "cursor": str(event["cursor"]),
                "correction_of": event.get("correction_of"),
                "reconciliation_id": event.get("reconciliation_id"),
                "payload": payload,
                "evidence": {
                    "replay_id": replay.id,
                    "replay_path": f"/v1/execution/replays/{replay.id}",
                    "receipt_id": receipt.id,
                    "receipt_path": (
                        f"/v1/research/quantitative-receipts/{receipt.id}"
                    ),
                    "receipt_digest": replay.receipt_digest,
                    "projection_digest": replay.projection_digest,
                    "event_digest": event["event_digest"],
                    "raw_reference_digest": event["raw_reference_digest"],
                },
            }
        )
    return events, {
        "replay_id": replay.id,
        "venue": replay.venue,
        "environment": replay.environment,
        "account_pseudonym": replay.account_pseudonym,
        "coverage": coverage,
        "event_count": len(events),
        "duplicates_suppressed": duplicate_count,
        "source_receipt_digest": replay.receipt_digest,
        "reason": (
            None
            if coverage == "complete"
            else "This immutable legacy replay retained a reduced projection, not event envelopes."
        ),
    }


def event_history(
    db: Session,
    *,
    environment: str | None = None,
    venue: str | None = None,
    replay_id: UUID | None = None,
) -> dict[str, Any]:
    query = select(ExecutionTelemetryReplay)
    if environment:
        query = query.where(ExecutionTelemetryReplay.environment == environment)
    if venue:
        query = query.where(ExecutionTelemetryReplay.venue == venue)
    if replay_id:
        query = query.where(ExecutionTelemetryReplay.id == replay_id)
    replays = db.scalars(
        query.order_by(
            ExecutionTelemetryReplay.observed_at,
            ExecutionTelemetryReplay.id,
        )
    ).all()
    receipt_digests = {item.receipt_digest for item in replays}
    receipts = (
        db.scalars(
            select(QuantitativeProducerReceipt).where(
                QuantitativeProducerReceipt.receipt_digest.in_(receipt_digests),
                QuantitativeProducerReceipt.milestone == "EXEC-011",
            )
        ).all()
        if receipt_digests
        else []
    )
    by_digest = {item.receipt_digest: item for item in receipts}
    events: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    duplicates = 0
    for replay in replays:
        receipt = by_digest.get(replay.receipt_digest)
        if receipt is None:
            raise ExecutionTelemetryConflict(
                "Execution replay has no resolvable immutable EXEC-011 receipt."
            )
        normalized, replay_coverage = normalize_event_history(replay, receipt)
        events.extend(normalized)
        coverage.append(replay_coverage)
        duplicates += replay_coverage["duplicates_suppressed"]
    events.sort(
        key=lambda item: (
            item["observed_time"],
            item["venue"],
            item["stream"],
            item["sequence"],
            item["evidence"]["event_digest"],
        )
    )
    counts: dict[str, int] = {
        "events": len(events),
        "replays": len(replays),
        "complete_replays": sum(item["coverage"] == "complete" for item in coverage),
        "legacy_summary_only_replays": sum(
            item["coverage"] == "legacy_summary_only" for item in coverage
        ),
        "duplicates_suppressed": duplicates,
    }
    for item in events:
        key = f"event_type:{item['event_type']}"
        counts[key] = counts.get(key, 0) + 1
    return {
        "schema_version": "mission-control-venue-event-history-v1",
        "generated_at": datetime.now(UTC),
        "environment": environment,
        "venue": venue,
        "replay_id": replay_id,
        "events": events,
        "counts": counts,
        "replay_coverage": coverage,
        "claim_boundary": "Immutable EXEC-011 event evidence only. Legacy reduced projections are disclosed and never expanded into synthetic events.",
    }


def overview(db: Session, environment: str | None) -> dict:
    query = select(ExecutionTelemetryReplay)
    if environment:
        query = query.where(ExecutionTelemetryReplay.environment == environment)
    rows = db.scalars(query.order_by(ExecutionTelemetryReplay.observed_at.desc())).all()
    latest: dict[tuple[str, str, str], ExecutionTelemetryReplay] = {}
    for row in rows:
        latest.setdefault((row.venue, row.environment, row.account_pseudonym), row)
    venues = list(latest.values())
    counts = {"current": 0, "stale": 0, "degraded": 0}
    for row in venues:
        counts[row.status] += 1
    return {
        "generated_at": datetime.now(UTC),
        "environment": environment,
        "venues": venues,
        "counts": counts,
        "claim_boundary": "Canonical replay evidence only. Displayed venue state grants no capital, allocation, promotion, or order authority.",
    }
