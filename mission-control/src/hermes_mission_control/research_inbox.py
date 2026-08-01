from __future__ import annotations

from typing import Any

from .config import MissionControlSettings
from .control_plane import ControlPlaneClient, ControlPlaneError
from .research_upload import (
    ResearchUploadError,
    digest,
    extract_passages,
    safe_filename,
)

SUPPORTED = {".pdf", ".md", ".markdown", ".txt"}
CLASSIFICATIONS = {
    "books": ("textbook", "method"),
    "papers": ("paper", "empirical_evidence"),
    "prior-results": ("prior_report", "prior_result"),
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
            if path.stat().st_size > settings.upload_max_bytes:
                raise ResearchUploadError(
                    "The source exceeds the configured upload limit."
                )
            content = path.read_bytes()
            content_digest = digest(content)
            existing = await client.research_document_by_digest(content_digest)
            if existing is not None:
                item.update(
                    status="unchanged",
                    document_key=existing["document_key"],
                    content_digest=content_digest,
                )
            else:
                category = relative.parts[0] if len(relative.parts) > 1 else "papers"
                document_type, evidence_type = CLASSIFICATIONS.get(
                    category, CLASSIFICATIONS["papers"]
                )
                passages = extract_passages(path.name, content)
                filename = safe_filename(path.name)
                document_key = f"research-{content_digest[:24]}"
                bundle = await client.register_research_bundle(
                    {
                        "document": {
                            "document_key": document_key,
                            "title": path.stem.replace("_", " ").replace("-", " "),
                            "document_type": document_type,
                            "evidence_type": evidence_type,
                            "version": content_digest[:12],
                            "source_uri": f"mission-control-inbox://{relative.as_posix()}",
                            "content_digest": content_digest,
                            "metadata": {
                                "domains": ["systematic-research"],
                                "original_filename": filename,
                                "inbox_category": category,
                            },
                            "ingested_by": "founder-mission-control",
                        },
                        "chunks": [
                            {
                                "ordinal": passage.ordinal,
                                "section": passage.section,
                                "page": passage.page,
                                "line_start": passage.line_start,
                                "line_end": passage.line_end,
                                "text": passage.text,
                                "text_digest": digest(passage.text.encode()),
                                "metadata": {"domain": "systematic-research"},
                            }
                            for passage in passages
                        ],
                    }
                )
                item.update(
                    status="added",
                    document_key=bundle["document"]["document_key"],
                    content_digest=content_digest,
                    passages=len(passages),
                    document_type=document_type,
                    evidence_type=evidence_type,
                )
        except (OSError, ResearchUploadError) as exc:
            item.update(status="rejected", error=str(exc))
        except ControlPlaneError as exc:
            item.update(status="failed", error=str(exc))
        results.append(item)
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("added", "unchanged", "rejected", "failed")
    }
    return {
        "inbox": str(root),
        "domain": "systematic-research",
        "counts": counts,
        "files": results,
    }
