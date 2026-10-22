from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
_MAX_CONTENT_LINES = 200
_MAX_CONTENT_CHARS = 64 * 1024


class KnowledgePolicyError(ValueError):
    pass


class LocalGraphQueryError(ValueError):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


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
                    opaque_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    content TEXT,
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
            self._migrate_sources(db)
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
                "SELECT id, digest, opaque_id, version FROM sources WHERE path = ?",
                (str(path),),
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
                    SET title=?, digest=?, version=version + 1, content=?,
                        modified_at=?, indexed_at=?, confidentiality=?
                    WHERE id=?
                    """,
                    (
                        title,
                        digest,
                        text,
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
                        (path, opaque_id, title, digest, version, content,
                         modified_at, indexed_at, confidentiality)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        str(path),
                        secrets.token_urlsafe(24),
                        title,
                        digest,
                        text,
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
                citation=(f"{row['path']}#L{row['line_start']}-L{row['line_end']}"),
            )
            for row in rows
        ]

    def catalog(self, *, limit: int = 500) -> list[dict[str, object]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT opaque_id, title, digest, version, modified_at, indexed_at,
                       confidentiality
                FROM sources
                ORDER BY title COLLATE NOCASE
                LIMIT ?
                """,
                (min(max(limit, 1), 500),),
            ).fetchall()
        return [
            {
                **dict(row),
                "id": row["opaque_id"],
                "origin": "Private local source",
            }
            for row in rows
        ]

    def source_content(
        self, opaque_id: str, *, start: int = 1, limit: int = 100
    ) -> dict[str, object] | None:
        """Return a bounded private source range without exposing its local path."""
        bounded_limit = min(max(limit, 1), _MAX_CONTENT_LINES)
        with self._connect() as db:
            row = db.execute(
                """
                SELECT opaque_id, title, digest, version, content, modified_at,
                       indexed_at, confidentiality
                FROM sources WHERE opaque_id=?
                """,
                (opaque_id,),
            ).fetchone()
            if row is None:
                return None
            text = row["content"]
            if text is None:
                text = self._reconstruct_content(db, opaque_id)

        lines = str(text or "").splitlines()
        total = len(lines)
        end = min(total, start + bounded_limit - 1)
        selected = lines[start - 1 : end] if start <= total else []
        body = "\n".join(selected)
        truncated_by_size = len(body.encode("utf-8")) > _MAX_CONTENT_CHARS
        if truncated_by_size:
            body = body.encode("utf-8")[:_MAX_CONTENT_CHARS].decode(
                "utf-8", errors="ignore"
            )
        returned_end = end if selected else 0
        citation = (
            f"private:{row['opaque_id']}@v{row['version']}"
            f"#L{start}-L{returned_end}"
        )
        return {
            "schema_version": "mission-control-source-content-v1.0.0",
            "source_kind": "private",
            "source_id": row["opaque_id"],
            "version": str(row["version"]),
            "source_digest": row["digest"],
            "content_digest": hashlib.sha256(
                str(text or "").encode("utf-8")
            ).hexdigest(),
            "title": row["title"],
            "access_class": row["confidentiality"],
            "content": body,
            "range": {
                "unit": "line",
                "start": start,
                "end": returned_end,
                "total": total,
                "limit": bounded_limit,
                "next_start": end + 1 if end < total else None,
                "truncated_by_size": truncated_by_size,
            },
            "citation": citation,
            "citations": [citation],
            "source_metadata": {
                "modified_at": row["modified_at"],
                "indexed_at": row["indexed_at"],
            },
            "lineage": {
                "extraction_method": "local-utf8-line-index",
                "parser": "hermes-private-knowledge-v1",
                "source_digest": row["digest"],
                "quality": "native_text",
                "uncertainties": [],
            },
            "outline": _private_outline(lines),
            "original_assets": [
                {
                    "availability": "unavailable",
                    "reason": "private_source_asset_not_exposed",
                }
            ],
        }

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

    def graph_overview(
        self, *, limit: int = 100, cursor: str | None = None
    ) -> dict[str, object]:
        nodes, edges, corpus_digest = self._private_graph_records()
        ordered = sorted(nodes)
        fingerprint = _digest(
            {"corpus_digest": corpus_digest, "mode": "overview", "limit": limit}
        )
        offset = _decode_cursor(cursor, fingerprint)
        if offset > len(ordered):
            raise LocalGraphQueryError("Private graph cursor is out of range.")
        page_ids = ordered[offset : offset + limit]
        selected = set(page_ids)
        selected_edges = [
            edge
            for edge in edges
            if edge["source"] in selected and edge["target"] in selected
        ]
        next_offset = offset + len(page_ids)
        next_cursor = (
            _encode_cursor(next_offset, fingerprint)
            if next_offset < len(ordered)
            else None
        )
        reasons = ["page_size"] if next_cursor else []
        return _private_graph_response(
            corpus_digest=corpus_digest,
            query={"mode": "overview", "limit": limit},
            nodes=[nodes[item] for item in page_ids],
            edges=selected_edges,
            paths=[],
            cursor=cursor,
            next_cursor=next_cursor,
            offset=offset,
            page_size=limit,
            traversed=len(ordered),
            reasons=reasons,
            max_nodes=limit,
            max_depth=1,
        )

    def query_graph(self, query: dict[str, Any]) -> dict[str, object]:
        nodes, edges, corpus_digest = self._private_graph_records()
        roots = list(query["root_ids"])
        target = query.get("target_id")
        requested = {*roots, *([target] if target else [])}
        object_types = set(query.get("object_types") or [])
        allowed_nodes = {
            key: node
            for key, node in nodes.items()
            if not object_types or node["object_type"] in object_types
        }
        if not requested <= set(allowed_nodes):
            raise LocalGraphQueryError(
                "Private graph root or target is unavailable.", status_code=404
            )
        predicates = set(query.get("predicates") or [])
        direction = query.get("direction", "both")
        filtered_edges = [
            edge
            for edge in edges
            if edge["source"] in allowed_nodes
            and edge["target"] in allowed_nodes
            and (not predicates or edge["predicate"] in predicates)
        ]
        adjacency: dict[str, list[str]] = {}
        for edge in filtered_edges:
            if direction in {"outgoing", "both"}:
                adjacency.setdefault(str(edge["source"]), []).append(
                    str(edge["target"])
                )
            if direction in {"incoming", "both"}:
                adjacency.setdefault(str(edge["target"]), []).append(
                    str(edge["source"])
                )
        for neighbors in adjacency.values():
            neighbors.sort()

        max_depth = int(query.get("max_depth", 2))
        max_nodes = int(query.get("max_nodes", 100))
        mode = str(query.get("mode", "neighborhood"))
        visited: list[str] = []
        seen: set[str] = set()
        paths: list[list[str]] = []
        depth_limited = False
        queue = deque((root, [root], 0) for root in roots)
        while queue and len(visited) <= max_nodes:
            node_id, path, depth = queue.popleft()
            if node_id not in seen:
                seen.add(node_id)
                visited.append(node_id)
            if mode == "paths" and node_id == target:
                paths.append(path)
                continue
            neighbors = adjacency.get(node_id, [])
            if depth >= max_depth:
                depth_limited = depth_limited or bool(neighbors)
                continue
            for neighbor in neighbors:
                if neighbor not in path:
                    queue.append((neighbor, [*path, neighbor], depth + 1))

        node_limited = len(visited) > max_nodes or bool(queue)
        ordered = visited[:max_nodes]
        fingerprint = _digest(
            {
                "corpus_digest": corpus_digest,
                "query": {
                    key: value
                    for key, value in query.items()
                    if key not in {"cursor", "page_size"}
                },
            }
        )
        cursor = query.get("cursor")
        offset = _decode_cursor(cursor, fingerprint)
        if offset > len(ordered):
            raise LocalGraphQueryError("Private graph cursor is out of range.")
        page_size = int(query.get("page_size", 50))
        page_ids = ordered[offset : offset + page_size]
        selected = set(page_ids)
        if offset:
            selected.update(roots)
        selected_edges = [
            edge
            for edge in filtered_edges
            if edge["source"] in selected and edge["target"] in selected
        ]
        next_offset = offset + len(page_ids)
        next_cursor = (
            _encode_cursor(next_offset, fingerprint)
            if next_offset < len(ordered)
            else None
        )
        reasons = []
        if next_cursor:
            reasons.append("page_size")
        if node_limited:
            reasons.append("max_nodes")
        if depth_limited:
            reasons.append("max_depth")
        return _private_graph_response(
            corpus_digest=corpus_digest,
            query=query,
            nodes=[nodes[item] for item in sorted(selected)],
            edges=selected_edges,
            paths=[path for path in paths if set(path) <= selected],
            cursor=cursor,
            next_cursor=next_cursor,
            offset=offset,
            page_size=page_size,
            traversed=len(ordered),
            reasons=reasons,
            max_nodes=max_nodes,
            max_depth=max_depth,
        )

    def _private_graph_records(
        self,
    ) -> tuple[dict[str, dict[str, object]], list[dict[str, object]], str]:
        with self._connect() as db:
            sources = db.execute(
                """
                SELECT id, opaque_id, title, digest, version, confidentiality
                FROM sources ORDER BY opaque_id
                """
            ).fetchall()
            relationships = db.execute(
                """
                SELECT s.opaque_id, s.digest, s.version, s.confidentiality,
                       t.name AS target_name, t.normalized_name, t.kind,
                       r.relation
                FROM relationships r
                JOIN sources s ON s.id = r.source_id
                JOIN entities t ON t.id = r.target_entity_id
                ORDER BY s.opaque_id, t.normalized_name, r.relation
                """
            ).fetchall()
        nodes: dict[str, dict[str, object]] = {}
        source_by_opaque = {str(row["opaque_id"]): row for row in sources}
        for row in sources:
            node_id = _private_source_node_id(str(row["opaque_id"]))
            nodes[node_id] = {
                "id": node_id,
                "object_type": "private_source",
                "project": "local-private",
                "access_class": row["confidentiality"],
                "content_digest": row["digest"],
                "label": row["title"],
                "replay_path": (
                    f"/api/knowledge/sources/private/{row['opaque_id']}/content"
                ),
                "scope": "private",
                "local_only": True,
            }
        edges: list[dict[str, object]] = []
        for row in relationships:
            source_id = _private_source_node_id(str(row["opaque_id"]))
            target_id = _private_entity_node_id(
                str(row["normalized_name"]), str(row["kind"])
            )
            nodes[target_id] = {
                "id": target_id,
                "object_type": f"private_{row['kind']}",
                "project": "local-private",
                "access_class": row["confidentiality"],
                "content_digest": _digest(
                    {
                        "name": row["normalized_name"],
                        "kind": row["kind"],
                    }
                ),
                "label": row["target_name"],
                "replay_path": nodes[source_id]["replay_path"],
                "scope": "private",
                "local_only": True,
            }
            edge_id = "private-edge:" + _digest(
                {
                    "source": source_id,
                    "target": target_id,
                    "predicate": row["relation"],
                }
            )[:40]
            source = source_by_opaque[str(row["opaque_id"])]
            record_digest = _digest(
                {
                    "edge_id": edge_id,
                    "source_digest": source["digest"],
                    "source_version": source["version"],
                }
            )
            edges.append(
                {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "predicate": row["relation"],
                    "valid_from": None,
                    "valid_until": None,
                    "provenance_object_id": source_id,
                    "access_class": row["confidentiality"],
                    "record_digest": record_digest,
                    "provenance": {
                        "source_id": source_id,
                        "source_digest": source["digest"],
                        "source_version": str(source["version"]),
                        "citation": (
                            f"private:{row['opaque_id']}@v{source['version']}"
                        ),
                        "local_only": True,
                    },
                }
            )
        edges.sort(key=lambda item: str(item["id"]))
        corpus_digest = _digest(
            {
                "nodes": [
                    (key, nodes[key]["content_digest"]) for key in sorted(nodes)
                ],
                "edges": [edge["record_digest"] for edge in edges],
            }
        )
        return nodes, edges, corpus_digest

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
            raise KnowledgePolicyError(
                "Only Markdown and UTF-8 text files are supported."
            )
        if not any(path.is_relative_to(root) for root in self.allowed_roots):
            raise KnowledgePolicyError("Knowledge source is outside approved roots.")
        return path

    @staticmethod
    def _migrate_sources(db: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(sources)").fetchall()
        }
        if "opaque_id" not in columns:
            db.execute("ALTER TABLE sources ADD COLUMN opaque_id TEXT")
        if "version" not in columns:
            db.execute(
                "ALTER TABLE sources ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
            )
        if "content" not in columns:
            db.execute("ALTER TABLE sources ADD COLUMN content TEXT")
        missing = db.execute(
            "SELECT id FROM sources WHERE opaque_id IS NULL OR opaque_id=''"
        ).fetchall()
        for row in missing:
            db.execute(
                "UPDATE sources SET opaque_id=? WHERE id=?",
                (secrets.token_urlsafe(24), row["id"]),
            )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_opaque_id "
            "ON sources(opaque_id)"
        )

    @staticmethod
    def _reconstruct_content(db: sqlite3.Connection, opaque_id: str) -> str:
        rows = db.execute(
            """
            SELECT c.line_start, c.line_end, c.body
            FROM chunks c JOIN sources s ON s.id=c.source_id
            WHERE s.opaque_id=? ORDER BY c.ordinal
            """,
            (opaque_id,),
        ).fetchall()
        total = max((row["line_end"] for row in rows), default=0)
        lines = [""] * total
        for row in rows:
            for offset, value in enumerate(row["body"].splitlines()):
                index = row["line_start"] - 1 + offset
                if index < total:
                    lines[index] = value
        return "\n".join(lines)

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


def _private_outline(lines: list[str]) -> list[dict[str, object]]:
    outline = []
    for number, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            outline.append(
                {
                    "label": match.group(2)[:200],
                    "level": len(match.group(1)),
                    "unit": "line",
                    "position": number,
                    "citation": f"L{number}",
                }
            )
    return outline[:500]


def _private_source_node_id(opaque_id: str) -> str:
    return f"private-source:{opaque_id}"


def _private_entity_node_id(normalized_name: str, kind: str) -> str:
    identity = hashlib.sha256(f"{kind}\0{normalized_name}".encode()).hexdigest()
    return f"private-entity:{identity[:40]}"


def _digest(document: object) -> str:
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _encode_cursor(offset: int, fingerprint: str) -> str:
    encoded = json.dumps(
        {"fingerprint": fingerprint, "offset": offset},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None, fingerprint: str) -> int:
    if cursor is None:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        document = json.loads(base64.urlsafe_b64decode(cursor + padding))
        offset = document["offset"]
        if (
            document.get("fingerprint") != fingerprint
            or not isinstance(offset, int)
            or isinstance(offset, bool)
            or offset < 0
        ):
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise LocalGraphQueryError(
            "Private graph cursor does not match this query."
        ) from exc
    return offset


def _private_graph_response(
    *,
    corpus_digest: str,
    query: dict[str, Any],
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    paths: list[list[str]],
    cursor: str | None,
    next_cursor: str | None,
    offset: int,
    page_size: int,
    traversed: int,
    reasons: list[str],
    max_nodes: int,
    max_depth: int,
) -> dict[str, object]:
    result_identity = {
        "scope": "private",
        "corpus_digest": corpus_digest,
        "query": query,
        "node_ids": [item["id"] for item in nodes],
        "edge_digests": [item["record_digest"] for item in edges],
    }
    return {
        "scope": "private",
        "projection_version": "mission-control-private-graph-v1.0.0",
        "corpus_digest": corpus_digest,
        "query_digest": _digest(result_identity),
        "nodes": nodes,
        "edges": edges,
        "paths": paths,
        "truncated": bool(reasons),
        "page": {
            "cursor": cursor,
            "next_cursor": next_cursor,
            "page_size": page_size,
            "offset": offset,
            "returned": len(nodes),
            "traversed": traversed,
        },
        "truncation": {
            "truncated": bool(reasons),
            "reasons": reasons,
            "max_nodes": max_nodes,
            "max_depth": max_depth,
        },
        "authorization": {
            "boundary": "mission-control-local-only",
            "mixed_scope_allowed": False,
        },
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
