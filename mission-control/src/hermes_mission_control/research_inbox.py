from __future__ import annotations

import base64
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MissionControlSettings
from .control_plane import ControlPlaneClient, ControlPlaneError
from .research_upload import ResearchUploadError, digest, safe_filename

SUPPORTED = {".pdf", ".md", ".markdown", ".txt"}
CLASSIFICATIONS = {
    "books": ("textbook", "method"),
    "papers": ("paper", "empirical_evidence"),
    "imported-prior-results": ("prior_report", "prior_result"),
    "governing": ("prd", "governing_requirement"),
}


def research_inbox_status(settings: MissionControlSettings) -> dict[str, Any]:
    state = _load_index(settings.research_inbox_index_path)
    return {
        "index": str(settings.research_inbox_index_path),
        "run": state.get("run", {"status": "not_started"}),
        "indexed_files": len(state["entries"]),
        "projection_cached": state.get("projection") is not None,
    }


async def sync_research_inbox(
    settings: MissionControlSettings,
    client: ControlPlaneClient,
    *,
    finalize_only: bool = False,
) -> dict[str, Any]:
    root = settings.research_inbox
    paths = [
        path
        for path in sorted(root.rglob("*"))
        if not path.name.startswith(".") and path.suffix.lower() in SUPPORTED
    ]
    with settings.research_inbox_lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ResearchUploadError(
                "A research inbox refresh is already running."
            ) from exc
        state = _load_index(settings.research_inbox_index_path)
        entries: dict[str, Any] = state["entries"]
        corpus_changed = bool(state.get("projection_dirty", False))
        if finalize_only:
            results = await _finalize_results(root, paths, state, client)
            state["run"] = _progress(
                "finalizing", total=len(paths), scanned=len(results), results=results
            )
            _save_index(settings.research_inbox_index_path, state)
        else:
            digest_entries = {
                entry["item"].get("content_digest"): entry
                for entry in entries.values()
                if entry.get("item", {}).get("disposition") == "canonical"
            }
            results = []
            state["run"] = _progress("running", total=len(paths), scanned=0, results=[])
            _save_index(settings.research_inbox_index_path, state)
            for path in paths:
                relative = path.relative_to(root)
                key = relative.as_posix()
                item, entry, changed = await _sync_path(
                    settings,
                    client,
                    root,
                    path,
                    relative,
                    entries.get(key),
                    digest_entries,
                )
                results.append(item)
                entries[key] = entry
                if item.get("disposition") == "canonical":
                    digest_entries[item["content_digest"]] = entry
                corpus_changed = corpus_changed or changed
                state["projection_dirty"] = corpus_changed
                state["run"] = _progress(
                    "running", total=len(paths), scanned=len(results), results=results
                )
                _save_index(settings.research_inbox_index_path, state)

        current_keys = {path.relative_to(root).as_posix() for path in paths}
        state["entries"] = {
            key: entry for key, entry in entries.items() if key in current_keys
        }
        reconciliation = await client.reconcile_corpus(
            {
                "schema_version": "corpus-sync-v1.0.0",
                "project": "systematic-research",
                "source_kind": "founder_inbox",
                "source_root": "mission-control-inbox",
                "requested_by": "founder-mission-control",
                "items": [_inventory_item(item) for item in results],
            }
        )
        projection = state.get("projection")
        projection_rebuilt = corpus_changed or projection is None
        if projection_rebuilt:
            projection = await client.rebuild_corpus_projections("systematic-research")
            state["projection"] = projection
            state["projection_dirty"] = False
        state["run"] = _progress(
            "complete", total=len(paths), scanned=len(results), results=results
        )
        state["run"]["coverage_digest"] = reconciliation["coverage_digest"]
        _save_index(settings.research_inbox_index_path, state)
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("added", "unchanged", "rejected", "failed")
    }
    return {
        "inbox": str(root),
        "domain": "systematic-research",
        "counts": counts,
        "files": results,
        "coverage": {
            "run_id": reconciliation["id"],
            "status": reconciliation["status"],
            "counts": reconciliation["counts"],
            "digest": reconciliation["coverage_digest"],
            "projection": projection["evidence"],
        },
        "incremental": {
            "corpus_changed": corpus_changed,
            "projection_rebuilt": projection_rebuilt,
            "index": str(settings.research_inbox_index_path),
        },
    }


async def _finalize_results(
    root: Path,
    paths: list[Path],
    state: dict[str, Any],
    client: ControlPlaneClient,
) -> list[dict[str, Any]]:
    entries: dict[str, Any] = state["entries"]
    run = state.get("run", {})
    keys = [path.relative_to(root).as_posix() for path in paths]
    if (
        run.get("scanned") != len(paths)
        or run.get("total") != len(paths)
        or set(entries) != set(keys)
    ):
        raise ResearchUploadError(
            "Finalize-only requires a complete checkpoint for the current inbox."
        )
    results = []
    for path, key in zip(paths, keys):
        entry = entries[key]
        if entry.get("fingerprint") != _safe_fingerprint(path):
            raise ResearchUploadError(f"Inbox source changed after checkpoint: {key}")
        item = dict(entry["item"])
        item["path"] = key
        item, changed = await _resolve_recovery(client, item)
        if changed:
            entry["item"] = item
            entry["synced_at"] = _now()
        results.append(item)
    return results


async def _sync_path(
    settings: MissionControlSettings,
    client: ControlPlaneClient,
    root: Path,
    path: Path,
    relative: Path,
    cached: dict[str, Any] | None,
    digest_entries: dict[str | None, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    item: dict[str, Any] = {"path": relative.as_posix()}
    try:
        if path.is_symlink() or not path.is_file():
            raise ResearchUploadError("Inbox sources must be regular files.")
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ResearchUploadError("Inbox source escapes the configured folder.")
        if relative.parts[0] == "prior-results":
            raise ResearchUploadError(
                "Move legacy or external reports to imported-prior-results. "
                "Bulletproof results are synchronized through the structured "
                "research-memory bridge."
            )
        stat = path.stat()
        if stat.st_size > settings.upload_max_bytes:
            raise ResearchUploadError("The source exceeds the configured upload limit.")
        fingerprint = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns,
        }
        if cached and cached.get("fingerprint") == fingerprint and _terminal(cached):
            cached_item = dict(cached["item"])
            cached_item.update(path=relative.as_posix(), status="unchanged")
            return cached_item, cached, False

        content = path.read_bytes()
        content_digest = digest(content)
        duplicate = digest_entries.get(content_digest)
        if duplicate is not None:
            duplicate_item = dict(duplicate["item"])
            duplicate_item.update(path=relative.as_posix(), status="unchanged")
            return (
                duplicate_item,
                {
                    "fingerprint": fingerprint,
                    "item": duplicate_item,
                    "synced_at": _now(),
                },
                False,
            )

        category = relative.parts[0] if len(relative.parts) > 1 else "papers"
        document_type, evidence_type = CLASSIFICATIONS.get(
            category, CLASSIFICATIONS["papers"]
        )
        job = await client.scientific_ingestion_by_digest(content_digest)
        if job is None:
            job = await client.create_scientific_ingestion(
                {
                    "schema_version": "scientific-ingestion-v1.0.0",
                    "project": "systematic-research",
                    "filename": safe_filename(path.name),
                    "media_type": _media_type(path),
                    "content_base64": base64.b64encode(content).decode("ascii"),
                    "content_digest": content_digest,
                    "access_class": "internal",
                    "source": {
                        "title": path.stem.replace("_", " ").replace("-", " "),
                        "origin": f"mission-control-inbox://{relative.as_posix()}",
                        "rights": "founder-provided research source",
                        "acquired_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "edition_label": content_digest[:12],
                    },
                    "requested_by": "founder-mission-control",
                }
            )
        original_job = job
        recovery = None
        if job["status"] != "published":
            recovery = await client.recovered_scientific_ingestion(job["id"])
            if recovery is not None:
                job = recovery["sanitized_job"]
        was_published = job["status"] == "published"
        if job["status"] != "published":
            job = await client.process_scientific_ingestion(job["id"])
        disposition = "canonical" if job["status"] == "published" else "quarantined"
        item.update(
            status=(
                "unchanged"
                if was_published
                else "added"
                if disposition == "canonical"
                else "rejected"
            ),
            content_digest=job["content_digest"] if recovery else content_digest,
            original_content_digest=content_digest if recovery else None,
            original_ingestion_job_id=original_job["id"] if recovery else None,
            document_type=document_type,
            evidence_type=evidence_type,
            ingestion_job_id=job["id"],
            disposition=disposition,
            canonical_object_ids=job["published_object_ids"],
            stage_report=job["stage_report"] if disposition == "quarantined" else None,
        )
        return (
            item,
            {
                "fingerprint": fingerprint,
                "item": item,
                "synced_at": _now(),
            },
            not was_published and disposition == "canonical",
        )
    except (OSError, ResearchUploadError) as exc:
        item.update(status="rejected", error=str(exc))
    except ControlPlaneError as exc:
        item.update(status="failed", disposition="failed", error=str(exc))
    return (
        item,
        {
            "fingerprint": _safe_fingerprint(path),
            "item": item,
            "synced_at": _now(),
        },
        False,
    )


async def _resolve_recovery(
    client: ControlPlaneClient, item: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    if item.get("disposition") != "quarantined" or not item.get("ingestion_job_id"):
        return item, False
    resolution = await client.recovered_scientific_ingestion(item["ingestion_job_id"])
    if resolution is None:
        return item, False
    recovered = resolution["sanitized_job"]
    original_digest = item.get("original_content_digest") or item.get("content_digest")
    original_job_id = item.get("original_ingestion_job_id") or item["ingestion_job_id"]
    updated = dict(item)
    updated.update(
        status="added",
        disposition="canonical",
        content_digest=recovered["content_digest"],
        ingestion_job_id=recovered["id"],
        canonical_object_ids=recovered["published_object_ids"],
        stage_report=None,
        original_content_digest=original_digest,
        original_ingestion_job_id=original_job_id,
        recovery_id=resolution["recovery"]["id"],
    )
    return updated, True


def _terminal(entry: dict[str, Any]) -> bool:
    return entry.get("item", {}).get("disposition") in {"canonical", "duplicate"}


def _load_index(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") == 1 and isinstance(value.get("entries"), dict):
            return value
    except (OSError, ValueError, TypeError):
        pass
    return {"schema_version": 1, "entries": {}}


def _save_index(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def _progress(
    status: str, *, total: int, scanned: int, results: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "status": status,
        "total": total,
        "scanned": scanned,
        "remaining": total - scanned,
        "counts": {
            name: sum(item.get("status") == name for item in results)
            for name in ("added", "unchanged", "rejected", "failed")
        },
        "updated_at": _now(),
    }


def _safe_fingerprint(path: Path) -> dict[str, int]:
    try:
        stat = path.lstat()
        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns,
        }
    except OSError:
        return {"size": -1, "mtime_ns": -1, "ctime_ns": -1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _media_type(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
    }[path.suffix.lower()]


def _inventory_item(item: dict[str, Any]) -> dict[str, Any]:
    disposition = item.get("disposition")
    if disposition is None:
        disposition = "excluded" if item["status"] == "rejected" else "failed"
    return {
        "source_locator": item["path"],
        "content_digest": item.get("content_digest"),
        "classification": {
            key: item[key] for key in ("document_type", "evidence_type") if key in item
        },
        "access_class": "internal",
        "disposition": disposition,
        "ingestion_job_id": item.get("ingestion_job_id"),
        "detail": item.get("error"),
    }
