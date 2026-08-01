from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import httpx
import pytest

from swarm_worker.research_memory_bridge import (
    build_export,
    canonical_digest,
    sync_export,
)


def _memory(repository: Path) -> Path:
    subprocess.run(["git", "init", "-q", repository], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Test"], check=True
    )
    (repository / "README.md").write_text("memory", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "memory"], check=True
    )
    database = repository / "research.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE research_memory_trades (
          run_id TEXT, hypothesis_id TEXT, metrics_valid INTEGER
        );
        CREATE TABLE research_memory_state_buckets (
          state_key TEXT, bucket TEXT, setup_class TEXT, hypothesis_name TEXT,
          n_trades INTEGER, ev_r_net REAL, avg_cost_drag_r REAL,
          finding_type TEXT, confidence_score REAL
        );
        CREATE TABLE research_memory_candidates (
          candidate_id TEXT, hypothesis_name TEXT, run_id TEXT,
          candidate_status TEXT, rank_score REAL, promotion_score REAL,
          ev_r_net REAL, n_trades INTEGER, recommended_action TEXT,
          created_at TEXT
        );
        CREATE TABLE research_memory_recommendations (
          recommendation_type TEXT, target_type TEXT, target_id TEXT,
          hypothesis_name TEXT, setup_class TEXT, recommendation TEXT,
          evidence_score REAL, confidence REAL, status TEXT,
          human_approved INTEGER, created_at TEXT
        );
        INSERT INTO research_memory_trades VALUES ('run-1', 'hyp-1', 1);
        INSERT INTO research_memory_trades VALUES ('run-2', 'hyp-2', 0);
        INSERT INTO research_memory_state_buckets VALUES
          ('vol', 'high', 'trend', 'momentum', 40, 0.5, 0.1, 'edge', 0.8),
          ('spread', 'wide', 'reversal', 'reversal', 30, -0.4, 0.7, 'avoid', 0.9);
        INSERT INTO research_memory_candidates VALUES
          ('candidate-1', 'momentum', 'run-1', 'REJECTED', 0.2, 0.1,
           -0.2, 40, 'Retire candidate', '2026-08-01T00:00:00Z');
        INSERT INTO research_memory_recommendations VALUES
          ('ADD_GATE', 'setup', 'trend', 'momentum', 'trend',
           'Require liquid state', 0.8, 0.7, 'PROPOSED', 0,
           '2026-08-01T00:00:00Z');
        """
    )
    connection.commit()
    connection.close()
    return database


def test_build_export_preserves_bounded_negative_and_positive_memory(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "bulletproof_bt"
    repository.mkdir()
    database = _memory(repository)

    document = build_export(repository, database)

    assert document.counts.model_dump() == {
        "trades": 2,
        "invalid_trades": 1,
        "state_buckets": 2,
        "candidates": 1,
        "recommendations": 1,
    }
    assert document.strongest_states[0].bucket == "high"
    assert document.weakest_states[0].bucket == "wide"
    assert document.candidates[0].candidate_status == "REJECTED"
    assert document.run_ids == ["run-1", "run-2"]


def test_sync_is_idempotent_and_sends_no_token_in_content(tmp_path: Path) -> None:
    repository = tmp_path / "bulletproof_bt"
    repository.mkdir()
    document = build_export(repository, _memory(repository))
    export_digest = canonical_digest(document.model_dump(mode="json"))
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer very-secret-token-value"
        assert b"very-secret-token-value" not in request.content
        if request.url.path.endswith(export_digest):
            return httpx.Response(404)
        if request.url.path == "/v1/research/memory-exports":
            return httpx.Response(201, json={"id": "export-id"})
        if "/knowledge/documents/by-digest/" in request.url.path:
            return httpx.Response(404)
        if request.url.path == "/v1/research/knowledge/document-bundles":
            return httpx.Response(
                201,
                json={
                    "document": {"document_key": "bulletproof-memory-key"},
                    "chunk_count": 1,
                },
            )
        raise AssertionError(request.url.path)

    result = sync_export(
        document,
        api_url="http://control-plane.test/",
        token="very-secret-token-value",
        transport=httpx.MockTransport(handler),
    )

    assert result["export_id"] == "export-id"
    assert result["document_key"] == "bulletproof-memory-key"
    assert all(request.method in {"GET", "POST"} for request in calls)


def test_active_wal_and_symlink_are_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "bulletproof_bt"
    repository.mkdir()
    database = _memory(repository)
    wal = database.with_name(f"{database.name}-wal")
    wal.write_bytes(b"active writer")

    with pytest.raises(ValueError, match="being written"):
        build_export(repository, database)

    wal.unlink()
    link = repository / "memory-link.sqlite"
    link.symlink_to(database)
    with pytest.raises(ValueError, match="symlink"):
        build_export(repository, link)
