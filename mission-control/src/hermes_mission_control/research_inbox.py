from __future__ import annotations

import base64
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


async def sync_research_inbox(
    settings: MissionControlSettings, client: ControlPlaneClient
) -> dict[str, Any]:
    root = settings.research_inbox
    results: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.name.startswith(".") or path.suffix.lower() not in SUPPORTED:
            continue
        relative = path.relative_to(root)
        item: dict[str, Any] = {"path": str(relative)}
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
            if path.stat().st_size > settings.upload_max_bytes:
                raise ResearchUploadError(
                    "The source exceeds the configured upload limit."
                )
            content = path.read_bytes()
            content_digest = digest(content)
            category = relative.parts[0] if len(relative.parts) > 1 else "papers"
            document_type, evidence_type = CLASSIFICATIONS.get(
                category, CLASSIFICATIONS["papers"]
            )
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
                            path.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "edition_label": content_digest[:12],
                    },
                    "requested_by": "founder-mission-control",
                }
            )
            was_published = job["status"] == "published"
            if not was_published:
                job = await client.process_scientific_ingestion(job["id"])
            disposition = (
                "canonical" if job["status"] == "published" else "quarantined"
            )
            item.update(
                status="unchanged" if was_published else (
                    "added" if disposition == "canonical" else "rejected"
                ),
                content_digest=content_digest,
                document_type=document_type,
                evidence_type=evidence_type,
                ingestion_job_id=job["id"],
                disposition=disposition,
                canonical_object_ids=job["published_object_ids"],
                stage_report=job["stage_report"] if disposition == "quarantined" else None,
            )
        except (OSError, ResearchUploadError) as exc:
            item.update(status="rejected", error=str(exc))
        except ControlPlaneError as exc:
            item.update(status="failed", disposition="failed", error=str(exc))
        results.append(item)
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
    projection = await client.rebuild_corpus_projections("systematic-research")
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
    }


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
            key: item[key]
            for key in ("document_type", "evidence_type")
            if key in item
        },
        "access_class": "internal",
        "disposition": disposition,
        "ingestion_job_id": item.get("ingestion_job_id"),
        "detail": item.get("error"),
    }
