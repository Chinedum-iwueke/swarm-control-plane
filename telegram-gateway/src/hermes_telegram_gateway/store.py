from __future__ import annotations

import hashlib
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
                """
            )

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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
