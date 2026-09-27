from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models import CodexAuthRecoveryEvent, FounderNotification
from app.schemas.codex_auth import CodexAuthRecoveryReport
from app.services.codex_auth import report_recovery, request_retry


def recovery(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "runtime_key": "vm1-shared-alpha-codex",
        "state": "authentication_required",
        "generation": 0,
        "verification_uri": None,
        "device_code": None,
        "code_expires_at": None,
        "retry_requested_at": None,
        "retry_acknowledged_at": None,
        "last_probe_at": now,
        "authenticated_at": None,
        "failure_summary": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_device_attempt_creates_one_generation_scoped_notification() -> None:
    value = recovery()
    db = MagicMock()
    db.scalar.side_effect = [value, None]
    expires = datetime.now(UTC) + timedelta(minutes=15)

    report_recovery(
        db,
        CodexAuthRecoveryReport(
            runtime_key=value.runtime_key,
            state="awaiting_authorization",
            generation=1,
            verification_uri="https://auth.openai.com/codex/device",
            device_code="ABCD-EFGH1",
            code_expires_at=expires,
            failure_summary="Founder authorization is required.",
        ),
        actor="watcher",
    )

    additions = [call.args[0] for call in db.add.call_args_list]
    notification = next(
        item for item in additions if isinstance(item, FounderNotification)
    )
    event = next(item for item in additions if isinstance(item, CodexAuthRecoveryEvent))
    assert notification.deduplication_key.endswith(":1")
    assert notification.payload["device_code"] == "ABCD-EFGH1"
    assert "token" not in notification.payload
    assert event.generation == 1
    assert value.retry_acknowledged_at is not None


def test_retry_request_is_idempotent_until_watcher_acknowledges() -> None:
    value = recovery(state="expired", generation=2)
    db = MagicMock()

    request_retry(
        db,
        value,
        actor="founder-telegram",
        reason="Replace the expired one-time device code.",
    )
    requested = value.retry_requested_at
    request_retry(
        db,
        value,
        actor="founder-telegram",
        reason="Replace the expired one-time device code.",
    )

    assert value.retry_requested_at == requested
    assert db.add.call_count == 1
