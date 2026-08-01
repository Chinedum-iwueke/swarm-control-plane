from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryCounts(StrictModel):
    trades: int = Field(ge=0)
    invalid_trades: int = Field(ge=0)
    state_buckets: int = Field(ge=0)
    candidates: int = Field(ge=0)
    recommendations: int = Field(ge=0)


class MemoryState(StrictModel):
    state_key: str = Field(min_length=1, max_length=150)
    bucket: str = Field(min_length=1, max_length=150)
    setup_class: str | None = Field(default=None, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    n_trades: int = Field(ge=0)
    ev_r_net: float | None = None
    avg_cost_drag_r: float | None = None
    finding_type: str | None = Field(default=None, max_length=100)
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class MemoryCandidate(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    run_id: str | None = Field(default=None, max_length=150)
    candidate_status: str | None = Field(default=None, max_length=100)
    rank_score: float | None = None
    promotion_score: float | None = None
    ev_r_net: float | None = None
    n_trades: int | None = Field(default=None, ge=0)
    recommended_action: str | None = Field(default=None, max_length=2000)


class MemoryRecommendation(StrictModel):
    recommendation_type: str = Field(min_length=1, max_length=100)
    target_type: str = Field(min_length=1, max_length=100)
    target_id: str | None = Field(default=None, max_length=150)
    hypothesis_name: str | None = Field(default=None, max_length=300)
    setup_class: str | None = Field(default=None, max_length=150)
    recommendation: str = Field(min_length=1, max_length=4000)
    evidence_score: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str = Field(min_length=1, max_length=100)
    human_approved: bool


class MemoryExport(StrictModel):

    schema_version: Literal[1] = 1
    repository: Literal["bulletproof_bt"] = "bulletproof_bt"
    repository_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    database_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    counts: MemoryCounts
    run_ids: list[str]
    hypothesis_ids: list[str]
    strongest_states: list[MemoryState] = Field(max_length=100)
    weakest_states: list[MemoryState] = Field(max_length=100)
    candidates: list[MemoryCandidate] = Field(max_length=100)
    recommendations: list[MemoryRecommendation] = Field(max_length=100)


def canonical_digest(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_commit(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def _rows(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query).fetchall()]


def build_export(repository: Path, database: Path) -> MemoryExport:
    repository = repository.resolve(strict=True)
    database_input = database.expanduser()
    if database_input.is_symlink():
        raise ValueError("Research memory must not be a symlink.")
    database = database_input.resolve(strict=True)
    if not database.is_file():
        raise ValueError("Research memory must be a regular SQLite file.")
    initial_stat = database.stat()
    wal = database.with_name(f"{database.name}-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("Research memory is being written; retry after it is quiescent.")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required = {
            "research_memory_trades",
            "research_memory_state_buckets",
            "research_memory_candidates",
            "research_memory_recommendations",
        }
        if not required.issubset(tables):
            raise ValueError("SQLite file does not contain Bulletproof research memory.")
        counts = {
            "trades": connection.execute(
                "SELECT COUNT(*) FROM research_memory_trades"
            ).fetchone()[0],
            "invalid_trades": connection.execute(
                "SELECT COUNT(*) FROM research_memory_trades "
                "WHERE metrics_valid = 0"
            ).fetchone()[0],
            "state_buckets": connection.execute(
                "SELECT COUNT(*) FROM research_memory_state_buckets"
            ).fetchone()[0],
            "candidates": connection.execute(
                "SELECT COUNT(*) FROM research_memory_candidates"
            ).fetchone()[0],
            "recommendations": connection.execute(
                "SELECT COUNT(*) FROM research_memory_recommendations"
            ).fetchone()[0],
        }
        state_columns = (
            "state_key, bucket, setup_class, hypothesis_name, n_trades, ev_r_net, "
            "avg_cost_drag_r, finding_type, confidence_score"
        )
        candidate_columns = (
            "candidate_id, hypothesis_name, run_id, candidate_status, rank_score, "
            "promotion_score, ev_r_net, n_trades, recommended_action"
        )
        recommendation_columns = (
            "recommendation_type, target_type, target_id, hypothesis_name, "
            "setup_class, recommendation, evidence_score, confidence, status, "
            "CAST(human_approved AS INTEGER) AS human_approved"
        )
        strongest = _rows(
            connection,
            f"SELECT {state_columns} FROM research_memory_state_buckets "
            "WHERE ev_r_net IS NOT NULL ORDER BY ev_r_net DESC, n_trades DESC LIMIT 100",
        )
        weakest = _rows(
            connection,
            f"SELECT {state_columns} FROM research_memory_state_buckets "
            "WHERE ev_r_net IS NOT NULL ORDER BY ev_r_net ASC, n_trades DESC LIMIT 100",
        )
        candidates = _rows(
            connection,
            f"SELECT {candidate_columns} FROM research_memory_candidates "
            "ORDER BY created_at DESC LIMIT 100",
        )
        recommendations = _rows(
            connection,
            f"SELECT {recommendation_columns} FROM research_memory_recommendations "
            "ORDER BY created_at DESC LIMIT 100",
        )
        for item in recommendations:
            item["human_approved"] = bool(item["human_approved"])
        # Candidate memory is already bounded and run-oriented. Avoid DISTINCT scans
        # over the multi-gigabyte trade table during routine synchronization.
        run_ids = sorted(
            {item["run_id"] for item in candidates if item.get("run_id")}
            | {
                value
                for row in connection.execute(
                    "SELECT run_id FROM research_memory_trades "
                    "WHERE run_id IS NOT NULL LIMIT 500"
                )
                if (value := row[0])
            }
        )[:500]
        hypothesis_ids = sorted(
            {
                value
                for row in connection.execute(
                    "SELECT hypothesis_id FROM research_memory_trades "
                    "WHERE hypothesis_id IS NOT NULL LIMIT 500"
                )
                if (value := row[0])
            }
        )
    finally:
        connection.close()
    payload = {
        "repository_commit": repository_commit(repository),
        "database_digest": "0" * 64,
        "counts": counts,
        "run_ids": run_ids,
        "hypothesis_ids": hypothesis_ids,
        "strongest_states": strongest,
        "weakest_states": weakest,
        "candidates": candidates,
        "recommendations": recommendations,
    }
    MemoryExport.model_validate(payload)
    payload["database_digest"] = file_digest(database)
    final_stat = database.stat()
    if (
        (initial_stat.st_ino, initial_stat.st_size, initial_stat.st_mtime_ns)
        != (final_stat.st_ino, final_stat.st_size, final_stat.st_mtime_ns)
        or (wal.exists() and wal.stat().st_size)
    ):
        raise ValueError("Research memory changed during export; retry the sync.")
    return MemoryExport.model_validate(payload)


def memory_summary(document: MemoryExport, export_digest: str) -> str:
    counts = document.counts.model_dump()
    lines = [
        "# Bulletproof Research Memory Export",
        "",
        f"Export digest: {export_digest}",
        f"Repository commit: {document.repository_commit}",
        f"Database digest: {document.database_digest}",
        "",
        "## Coverage",
        "",
        *(f"- {name.replace('_', ' ').title()}: {value}" for name, value in counts.items()),
        "",
        "## Strongest states",
        "",
    ]
    for record in document.strongest_states[:20]:
        item = record.model_dump()
        lines.append(
            f"- {item['state_key']}={item['bucket']}; setup={item.get('setup_class')}; "
            f"n={item['n_trades']}; ev_r_net={item.get('ev_r_net')}"
        )
    lines.extend(["", "## Weakest states", ""])
    for record in document.weakest_states[:20]:
        item = record.model_dump()
        lines.append(
            f"- {item['state_key']}={item['bucket']}; setup={item.get('setup_class')}; "
            f"n={item['n_trades']}; ev_r_net={item.get('ev_r_net')}"
        )
    lines.extend(["", "## Recommendations", ""])
    for record in document.recommendations[:20]:
        item = record.model_dump()
        lines.append(
            f"- [{item['status']}] {item['recommendation_type']}: "
            f"{item['recommendation']}"
        )
    lines.extend(
        [
            "",
            "This is a bounded, evidence-only projection. Full trade memory remains ",
            "authoritative in bulletproof_bt and no promotion or trading authority is granted.",
        ]
    )
    return "\n".join(lines)[:19_000]


def sync_export(
    document: MemoryExport,
    *,
    api_url: str,
    token: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    export = document.model_dump(mode="json")
    export_digest = canonical_digest(export)
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(
        base_url=api_url.rstrip("/"),
        headers=headers,
        timeout=60,
        transport=transport,
    ) as client:
        existing = client.get(f"/v1/research/memory-exports/by-digest/{export_digest}")
        if existing.status_code == 404:
            response = client.post(
                "/v1/research/memory-exports",
                json={
                    "export": export,
                    "export_digest": export_digest,
                    "registered_by": "bulletproof-memory-bridge",
                },
            )
            if response.status_code != 201:
                raise RuntimeError(
                    f"Memory export registration returned HTTP {response.status_code}."
                )
            export_record = response.json()
        elif existing.status_code == 200:
            export_record = existing.json()
        else:
            raise RuntimeError(
                f"Memory export lookup returned HTTP {existing.status_code}."
            )
        summary = memory_summary(document, export_digest)
        summary_digest = hashlib.sha256(summary.encode()).hexdigest()
        indexed = client.get(
            f"/v1/research/knowledge/documents/by-digest/{summary_digest}"
        )
        if indexed.status_code == 404:
            response = client.post(
                "/v1/research/knowledge/document-bundles",
                json={
                    "document": {
                        "document_key": f"bulletproof-memory-{export_digest[:24]}",
                        "title": "Bulletproof Research Memory",
                        "document_type": "prior_report",
                        "evidence_type": "prior_result",
                        "version": export_digest[:12],
                        "source_uri": f"bulletproof-memory://{export_digest}",
                        "content_digest": summary_digest,
                        "metadata": {
                            "domains": ["systematic-research"],
                            "export_digest": export_digest,
                            "repository_commit": document.repository_commit,
                            "database_digest": document.database_digest,
                        },
                        "ingested_by": "bulletproof-memory-bridge",
                    },
                    "chunks": [
                        {
                            "ordinal": 0,
                            "section": "Research memory summary",
                            "page": None,
                            "line_start": 1,
                            "line_end": len(summary.splitlines()),
                            "text": summary,
                            "text_digest": summary_digest,
                            "metadata": {"domain": "systematic-research"},
                        }
                    ],
                },
            )
            if response.status_code != 201:
                raise RuntimeError(
                    f"Memory summary registration returned HTTP {response.status_code}."
                )
            knowledge_record = response.json()
        elif indexed.status_code == 200:
            knowledge_record = {"document": indexed.json(), "chunk_count": 1}
        else:
            raise RuntimeError(
                f"Memory summary lookup returned HTTP {indexed.status_code}."
            )
    return {
        "export_digest": export_digest,
        "export_id": export_record["id"],
        "document_key": knowledge_record["document"]["document_key"],
        "counts": document.counts.model_dump(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Bulletproof research memory")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    document = build_export(args.repository, args.database)
    export = document.model_dump(mode="json")
    export_digest = canonical_digest(export)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.output.write_text(
            json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        args.output.chmod(0o600)
    if args.dry_run:
        result = {
            "export_digest": export_digest,
            "counts": document.counts.model_dump(),
        }
    else:
        result = sync_export(
            document,
            api_url=os.environ["SWARM_API_URL"],
            token=os.environ["SWARM_ORCHESTRATOR_TOKEN"],
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
