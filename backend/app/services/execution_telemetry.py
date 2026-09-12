import hashlib
import json
from datetime import UTC, datetime

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


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


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
