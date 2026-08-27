from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path


class HandoffStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS handoffs (
                    token_digest TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_digest TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS seen (
                    entity_key TEXT PRIMARY KEY,
                    state_digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS values_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    notification_id TEXT PRIMARY KEY,
                    delivery_reference TEXT NOT NULL,
                    delivered_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS founder_rate_events (
                    occurred_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_founder_rate_events_occurred_at
                    ON founder_rate_events(occurred_at);
                CREATE TABLE IF NOT EXISTS channel_security_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    prior_digest TEXT NOT NULL,
                    event_digest TEXT NOT NULL UNIQUE
                );
                """
            )

    def notification_delivery(self, notification_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT delivery_reference FROM notification_deliveries WHERE notification_id = ?",
                (notification_id,),
            ).fetchone()
        return row[0] if row else None

    def mark_notification_delivered(
        self, notification_id: str, delivery_reference: str
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO notification_deliveries
                    (notification_id, delivery_reference, delivered_at)
                VALUES (?, ?, ?)
                ON CONFLICT(notification_id) DO NOTHING
                """,
                (notification_id, delivery_reference, int(time.time())),
            )

    def admit_founder_message(
        self, *, limit: int, window_seconds: int, now: int | None = None
    ) -> bool:
        timestamp = int(time.time()) if now is None else now
        cutoff = timestamp - window_seconds
        with self._connect() as db:
            db.execute("DELETE FROM founder_rate_events WHERE occurred_at <= ?", (cutoff,))
            count = db.execute(
                "SELECT COUNT(*) FROM founder_rate_events WHERE occurred_at > ?",
                (cutoff,),
            ).fetchone()[0]
            if count >= limit:
                return False
            db.execute(
                "INSERT INTO founder_rate_events(occurred_at) VALUES (?)", (timestamp,)
            )
        return True

    def record_security_event(self, event_type: str, metadata: dict | None = None) -> str:
        safe_metadata = metadata or {}
        encoded = json.dumps(safe_metadata, separators=(",", ":"), sort_keys=True)
        now = int(time.time())
        with self._connect() as db:
            row = db.execute(
                "SELECT sequence, event_digest FROM channel_security_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence = int(row[0]) + 1 if row else 1
            prior = row[1] if row else "0" * 64
            material = f"{sequence}:{prior}:{now}:{event_type}:{encoded}".encode()
            event_digest = hashlib.sha256(material).hexdigest()
            db.execute(
                """
                INSERT INTO channel_security_events
                    (occurred_at, event_type, metadata_json, prior_digest, event_digest)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, event_type, encoded, prior, event_digest),
            )
        return event_digest

    def security_event_counts(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_type, COUNT(*) FROM channel_security_events GROUP BY event_type"
            ).fetchall()
        return {str(event_type): int(count) for event_type, count in rows}

    def verify_security_event_chain(self) -> tuple[bool, int, str]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT sequence, occurred_at, event_type, metadata_json,
                       prior_digest, event_digest
                FROM channel_security_events ORDER BY sequence
                """
            ).fetchall()
        prior = "0" * 64
        for sequence, occurred_at, event_type, metadata_json, stored_prior, digest in rows:
            material = (
                f"{sequence}:{prior}:{occurred_at}:{event_type}:{metadata_json}".encode()
            )
            expected = hashlib.sha256(material).hexdigest()
            if stored_prior != prior or digest != expected:
                return False, len(rows), prior
            prior = digest
        return True, len(rows), prior

    def create(
        self,
        entity_type: str,
        entity_id: str,
        entity_digest: str,
        ttl_seconds: int,
    ) -> str:
        token = secrets.token_urlsafe(24)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO handoffs
                (token_digest, entity_type, entity_id, entity_digest, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self._digest(token),
                    entity_type,
                    entity_id,
                    entity_digest,
                    int(time.time()) + ttl_seconds,
                ),
            )
        return token

    def resolve(self, token: str) -> tuple[str, str, str] | None:
        now = int(time.time())
        with self._connect() as db:
            row = db.execute(
                """
                SELECT entity_type, entity_id, entity_digest
                FROM handoffs
                WHERE token_digest = ? AND consumed_at IS NULL AND expires_at > ?
                """,
                (self._digest(token), now),
            ).fetchone()
        return tuple(row) if row is not None else None

    def consume(self, token: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE handoffs SET consumed_at = ?
                WHERE token_digest = ? AND consumed_at IS NULL
                """,
                (int(time.time()), self._digest(token)),
            )
        return cursor.rowcount == 1

    def changed(self, key: str, state_digest: str) -> bool:
        changed = self.is_changed(key, state_digest)
        self.mark_seen(key, state_digest)
        return changed

    def is_changed(self, key: str, state_digest: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT state_digest FROM seen WHERE entity_key = ?", (key,)
            ).fetchone()
        return row is None or row[0] != state_digest

    def mark_seen(self, key: str, state_digest: str) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO seen(entity_key, state_digest) VALUES (?, ?)
                ON CONFLICT(entity_key)
                DO UPDATE SET state_digest = excluded.state_digest
                """,
                (key, state_digest),
            )

    def set_value(self, key: str, value: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO values_store(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def pop_value(self, key: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM values_store WHERE key = ?", (key,)
            ).fetchone()
            db.execute("DELETE FROM values_store WHERE key = ?", (key,))
        return row[0] if row else None

    def get_value(self, key: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM values_store WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def polling_offset(self) -> int:
        value = self.get_value("telegram-update-offset")
        return int(value) if value is not None else 0

    def commit_polling_offset(self, offset: int) -> None:
        current = self.polling_offset()
        if offset < current:
            raise ValueError("Telegram polling offset cannot move backwards.")
        self.set_value("telegram-update-offset", str(offset))

    def bind_message(self, message_id: str, conversation_id: str) -> None:
        self.set_value(f"telegram-message:{message_id}", conversation_id)

    def conversation_for_message(self, message_id: str) -> str | None:
        return self.get_value(f"telegram-message:{message_id}")

    def bind_research_cycle(self, message_id: str, cycle: dict) -> None:
        self.set_value(
            f"telegram-research-cycle:{message_id}",
            json.dumps(cycle, separators=(",", ":"), sort_keys=True),
        )

    def research_cycle_for_message(self, message_id: str) -> dict | None:
        value = self.get_value(f"telegram-research-cycle:{message_id}")
        if value is None:
            return None
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None

    def hold_routing_draft(self, text: str, message_id: str | None) -> None:
        self.set_value(
            "pending-routing-draft",
            json.dumps({"text": text, "message_id": message_id}),
        )

    def pop_routing_draft(self) -> dict | None:
        value = self.pop_value("pending-routing-draft")
        if value is None:
            return None
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None

    def activate_conversation(self, conversation_id: str) -> None:
        self.set_value("selected-conversation-id", conversation_id)
        self.set_value("selected-conversation-active-at", str(int(time.time())))

    def conversation_session_active(
        self, conversation_id: str, *, ttl_seconds: int = 900
    ) -> bool:
        if self.get_value("selected-conversation-id") != conversation_id:
            return False
        value = self.get_value("selected-conversation-active-at")
        return value is not None and int(time.time()) - int(value) <= ttl_seconds

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
