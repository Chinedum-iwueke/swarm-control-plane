"""Source provenance and fail-closed freshness for Mission Control projections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FactClass = Literal["canonical", "derived", "cached", "inferred", "unavailable"]
FreshnessState = Literal["current", "stale", "unknown", "unavailable", "partial"]


class SourceFreshness(BaseModel):
    """The truth boundary for one source contributing to a dashboard snapshot."""

    model_config = ConfigDict(extra="forbid")

    source_key: str
    source_identity: str
    fact_class: FactClass
    freshness: FreshnessState
    freshness_threshold_seconds: int = Field(gt=0)
    source_timestamp: Optional[str] = None  # noqa: UP045 - Python 3.9 support.
    reason: Optional[str] = None  # noqa: UP045 - Python 3.9 support.


class SnapshotProvenance(BaseModel):
    """Versioned metadata shared by every aggregate Mission Control response."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mission-control-provenance-v1"] = (
        "mission-control-provenance-v1"
    )
    generated_at: str
    source_identity: Literal["mission-control/dashboard"] = "mission-control/dashboard"
    fact_class: Literal["derived"] = "derived"
    freshness: FreshnessState
    freshness_threshold_seconds: int = Field(gt=0)
    reason: Optional[str] = None  # noqa: UP045 - Python 3.9 support.
    sources: dict[str, SourceFreshness]


class SourceRule(BaseModel):
    source_identity: str
    fact_class: Literal["canonical", "derived"] = "canonical"
    freshness_threshold_seconds: int
    timestamp_fields: tuple[str, ...] = ()


# These rules are intentionally conservative. A collection with no generated,
# observation, heartbeat, or update timestamp is not treated as fresh merely
# because a request happened to succeed.
SOURCE_RULES: dict[str, SourceRule] = {
    "health": SourceRule(
        source_identity="control-plane:/health",
        freshness_threshold_seconds=60,
        timestamp_fields=("generated_at",),
    ),
    "tasks": SourceRule(
        source_identity="control-plane:/v1/tasks",
        freshness_threshold_seconds=120,
        timestamp_fields=("updated_at", "heartbeat_at"),
    ),
    "agents": SourceRule(
        source_identity="control-plane:/v1/agents",
        freshness_threshold_seconds=120,
        timestamp_fields=("last_heartbeat_at", "updated_at"),
    ),
    "fleet_health": SourceRule(
        source_identity="control-plane:/v1/fleet/health",
        freshness_threshold_seconds=180,
        timestamp_fields=("generated_at", "last_observed_at"),
    ),
    "observability": SourceRule(
        source_identity="control-plane:/v1/observability/overview",
        freshness_threshold_seconds=180,
        timestamp_fields=("generated_at", "evaluated_at", "updated_at"),
    ),
    "execution_telemetry": SourceRule(
        source_identity="control-plane:/v1/execution/overview",
        freshness_threshold_seconds=300,
        timestamp_fields=("generated_at", "observed_at"),
    ),
    "backtest_activity": SourceRule(
        source_identity="control-plane:/v1/research/alpha-campaigns/backtests/activity",
        freshness_threshold_seconds=300,
        timestamp_fields=("generated_at", "heartbeat_at", "updated_at"),
    ),
    "research_utilization": SourceRule(
        source_identity="control-plane:/v1/research/utilization/current",
        freshness_threshold_seconds=180,
        timestamp_fields=("generated_at", "observed_at"),
    ),
    "alpha_discovery": SourceRule(
        source_identity="control-plane:/v1/research/alpha-discovery/overview",
        freshness_threshold_seconds=300,
        timestamp_fields=("generated_at", "heartbeat_at", "updated_at"),
    ),
}


def build_snapshot_provenance(
    snapshot: dict[str, Any], *, now: datetime | None = None
) -> SnapshotProvenance:
    """Describe freshness without inventing timestamps or source confidence."""

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sources = {
        key: _source_freshness(key, rule, snapshot.get(key), now)
        for key, rule in SOURCE_RULES.items()
    }
    states = {item.freshness for item in sources.values()}
    if "stale" in states:
        freshness: FreshnessState = "stale"
        reason = "one_or_more_required_sources_stale"
    elif "unavailable" in states or "unknown" in states:
        freshness = "partial"
        reason = "one_or_more_required_sources_not_freshness_verified"
    else:
        freshness = "current"
        reason = None

    return SnapshotProvenance(
        generated_at=now.isoformat(),
        freshness=freshness,
        freshness_threshold_seconds=45,
        reason=reason,
        sources=sources,
    )


def _source_freshness(
    key: str, rule: SourceRule, value: Any, now: datetime
) -> SourceFreshness:
    if _is_unavailable(value):
        return SourceFreshness(
            source_key=key,
            source_identity=rule.source_identity,
            fact_class="unavailable",
            freshness="unavailable",
            freshness_threshold_seconds=rule.freshness_threshold_seconds,
            reason="source_unavailable",
        )

    timestamp = _latest_timestamp(value, rule.timestamp_fields)
    if timestamp is None:
        return SourceFreshness(
            source_key=key,
            source_identity=rule.source_identity,
            fact_class=rule.fact_class,
            freshness="unknown",
            freshness_threshold_seconds=rule.freshness_threshold_seconds,
            reason="source_timestamp_missing",
        )
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return SourceFreshness(
            source_key=key,
            source_identity=rule.source_identity,
            fact_class=rule.fact_class,
            freshness="unknown",
            freshness_threshold_seconds=rule.freshness_threshold_seconds,
            source_timestamp=timestamp,
            reason="source_timestamp_invalid",
        )
    if parsed > now:
        return SourceFreshness(
            source_key=key,
            source_identity=rule.source_identity,
            fact_class=rule.fact_class,
            freshness="unknown",
            freshness_threshold_seconds=rule.freshness_threshold_seconds,
            source_timestamp=timestamp,
            reason="source_timestamp_in_future",
        )
    age = (now - parsed).total_seconds()
    return SourceFreshness(
        source_key=key,
        source_identity=rule.source_identity,
        fact_class=rule.fact_class,
        freshness=("current" if age <= rule.freshness_threshold_seconds else "stale"),
        freshness_threshold_seconds=rule.freshness_threshold_seconds,
        source_timestamp=timestamp,
        reason=(
            None
            if age <= rule.freshness_threshold_seconds
            else "source_timestamp_stale"
        ),
    )


def _is_unavailable(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("unavailable"))


def _latest_timestamp(value: Any, fields: tuple[str, ...]) -> str | None:
    timestamps: list[datetime] = []
    serialized: dict[datetime, str] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for field in fields:
                candidate = item.get(field)
                if isinstance(candidate, str):
                    parsed = _parse_timestamp(candidate)
                    if parsed is not None:
                        timestamps.append(parsed)
                        serialized[parsed] = candidate
            for nested in item.values():
                if isinstance(nested, (dict, list)):
                    visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return serialized[max(timestamps)] if timestamps else None


def _parse_timestamp(value: str) -> Optional[datetime]:  # noqa: UP045 - Python 3.9.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
