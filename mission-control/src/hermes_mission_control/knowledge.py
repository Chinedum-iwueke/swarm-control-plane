from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    KnowledgeIngestResult,
    KnowledgeSearchResult,
)

_SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}
_WIKI_LINK = re.compile(r"\[\[([A-Za-z0-9][A-Za-z0-9 ._'-]{0,99})\]\]")
_HASHTAG = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]{1,49})")
_SEARCH_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,63}")
_MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
_MAX_CHUNK_CHARS = 1600


class KnowledgePolicyError(ValueError):
    pass


class KnowledgeStore:
    def __init__(self, database_path: Path, allowed_roots: tuple[Path, ...]) -> None:
        self.database_path = database_path
        self.allowed_roots = tuple(root.resolve() for root in allowed_roots)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    modified_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    confidentiality TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    UNIQUE(source_id, ordinal)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_search USING fts5(
                    body, source_id UNINDEXED, chunk_id UNINDEXED,
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    source_entity_id INTEGER NOT NULL REFERENCES entities(id),
                    target_entity_id INTEGER NOT NULL REFERENCES entities(id),
                    relation TEXT NOT NULL,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    UNIQUE(source_entity_id, target_entity_id, relation, source_id)
                );
                """
            )
        self.database_path.chmod(0o600)

    def ingest(
        self, raw_path: str, *, confidentiality: str = "private"
    ) -> KnowledgeIngestResult:
        path = self._resolve_source(raw_path)
        data = path.read_bytes()
        if len(data) > _MAX_DOCUMENT_BYTES:
            raise KnowledgePolicyError("Document exceeds the 5 MiB pilot limit.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgePolicyError("Document must be UTF-8 text.") from exc
        digest = hashlib.sha256(data).hexdigest()
        title = _title(path, text)
        modified_at = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        chunks = _chunks(text)
        entities = _entities(title, text)
        with self._connect() as db:
            existing = db.execute(
                "SELECT id, digest FROM sources WHERE path = ?", (str(path),)
            ).fetchone()
            if existing and existing["digest"] == digest:
                return KnowledgeIngestResult(
                    source_id=existing["id"],
                    title=title,
                    path=str(path),
                    digest=digest,
                    chunks=len(chunks),
                    entities=len(entities),
                    unchanged=True,
                )
            if existing:
                source_id = existing["id"]
                self._delete_source_content(db, source_id)
                db.execute(
                    """
                    UPDATE sources
                    SET title=?, digest=?, modified_at=?, indexed_at=?,
                        confidentiality=?
                    WHERE id=?
                    """,
                    (
                        title,
                        digest,
                        modified_at,
                        _now(),
                        confidentiality,
                        source_id,
                    ),
                )
            else:
                cursor = db.execute(
                    """
                    INSERT INTO sources
                        (path, title, digest, modified_at, indexed_at, confidentiality)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(path),
                        title,
                        digest,
                        modified_at,
                        _now(),
                        confidentiality,
                    ),
                )
                source_id = int(cursor.lastrowid)
            for ordinal, (line_start, line_end, body) in enumerate(chunks):
                cursor = db.execute(
                    """
                    INSERT INTO chunks
                        (source_id, ordinal, line_start, line_end, body)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (source_id, ordinal, line_start, line_end, body),
                )
                db.execute(
                    "INSERT INTO chunk_search(body, source_id, chunk_id) VALUES(?,?,?)",
                    (body, source_id, int(cursor.lastrowid)),
                )
            source_entity = self._entity(db, title, "document")
            for name, kind in entities:
                target = self._entity(db, name, kind)
                if target != source_entity:
                    db.execute(
                        """
                        INSERT OR IGNORE INTO relationships
                            (source_entity_id, target_entity_id, relation, source_id)
                        VALUES (?, ?, 'mentions', ?)
                        """,
                        (source_entity, target, source_id),
                    )
        return KnowledgeIngestResult(
            source_id=source_id,
            title=title,
            path=str(path),
            digest=digest,
            chunks=len(chunks),
            entities=len(entities),
            unchanged=False,
        )

    def search(self, query: str, *, limit: int = 12) -> list[KnowledgeSearchResult]:
        tokens = _SEARCH_TOKEN.findall(query)
        if not tokens:
            return []
        expression = " AND ".join(f'"{token}"' for token in tokens[:10])
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT s.id AS source_id, s.title, s.path, s.digest, s.modified_at,
                       c.line_start, c.line_end, c.body,
                       bm25(chunk_search) AS score
                FROM chunk_search
                JOIN chunks c ON c.id = chunk_search.chunk_id
                JOIN sources s ON s.id = c.source_id
                WHERE chunk_search MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (expression, min(max(limit, 1), 50)),
            ).fetchall()
        return [
            KnowledgeSearchResult(
                source_id=row["source_id"],
                title=row["title"],
                path=row["path"],
                digest=row["digest"],
                modified_at=row["modified_at"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                excerpt=row["body"][:1200],
                score=float(row["score"]),
                citation=(
                    f"{row['path']}#L{row['line_start']}-L{row['line_end']}"
                ),
            )
            for row in rows
        ]

    def graph(self, *, limit: int = 250) -> KnowledgeGraph:
        with self._connect() as db:
            node_rows = db.execute(
                "SELECT id, name, kind FROM entities ORDER BY name LIMIT ?",
                (min(max(limit, 1), 500),),
            ).fetchall()
            node_ids = {row["id"] for row in node_rows}
            edge_rows = db.execute(
                """
                SELECT source_entity_id, target_entity_id, relation
                FROM relationships
                ORDER BY source_entity_id, target_entity_id
                """
            ).fetchall()
        return KnowledgeGraph(
            nodes=[
                GraphNode(id=row["id"], name=row["name"], kind=row["kind"])
                for row in node_rows
            ],
            edges=[
                GraphEdge(
                    source=row["source_entity_id"],
                    target=row["target_entity_id"],
                    relation=row["relation"],
                )
                for row in edge_rows
                if row["source_entity_id"] in node_ids
                and row["target_entity_id"] in node_ids
            ],
        )

    def stats(self) -> dict[str, int]:
        with self._connect() as db:
            return {
                "sources": db.execute("SELECT count(*) FROM sources").fetchone()[0],
                "chunks": db.execute("SELECT count(*) FROM chunks").fetchone()[0],
                "entities": db.execute("SELECT count(*) FROM entities").fetchone()[0],
                "relationships": db.execute(
                    "SELECT count(*) FROM relationships"
                ).fetchone()[0],
            }

    def _resolve_source(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            raise KnowledgePolicyError("Knowledge source path must be absolute.")
        path = candidate.resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            raise KnowledgePolicyError("Only Markdown and UTF-8 text files are supported.")
        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            raise KnowledgePolicyError("Knowledge source is outside approved roots.")
        return path

    @staticmethod
    def _delete_source_content(db: sqlite3.Connection, source_id: int) -> None:
        chunk_ids = [
            row[0]
            for row in db.execute(
                "SELECT id FROM chunks WHERE source_id=?", (source_id,)
            )
        ]
        for chunk_id in chunk_ids:
            db.execute("DELETE FROM chunk_search WHERE chunk_id=?", (chunk_id,))
        db.execute("DELETE FROM relationships WHERE source_id=?", (source_id,))
        db.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))

    @staticmethod
    def _entity(db: sqlite3.Connection, name: str, kind: str) -> int:
        normalized = " ".join(name.casefold().split())
        db.execute(
            """
            INSERT INTO entities(name, normalized_name, kind) VALUES(?,?,?)
            ON CONFLICT(normalized_name) DO NOTHING
            """,
            (name.strip(), normalized, kind),
        )
        row = db.execute(
            "SELECT id FROM entities WHERE normalized_name=?", (normalized,)
        ).fetchone()
        return int(row[0])

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db


def _chunks(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    chunks: list[tuple[int, int, str]] = []
    start = 1
    buffer: list[str] = []
    for number, line in enumerate(lines, start=1):
        proposed = "\n".join((*buffer, line)).strip()
        if buffer and (not line.strip() or len(proposed) > _MAX_CHUNK_CHARS):
            body = "\n".join(buffer).strip()
            if body:
                chunks.append((start, number - 1, body))
            buffer = []
            start = number + 1 if not line.strip() else number
        if line.strip():
            buffer.append(line)
    if buffer:
        chunks.append((start, len(lines), "\n".join(buffer).strip()))
    return chunks or [(1, max(len(lines), 1), text.strip())]


def _title(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:200]
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _entities(title: str, text: str) -> set[tuple[str, str]]:
    values = {(title, "document")}
    values.update((match.strip(), "topic") for match in _WIKI_LINK.findall(text))
    values.update((match.replace("-", " "), "tag") for match in _HASHTAG.findall(text))
    return values


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

