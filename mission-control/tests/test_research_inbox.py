from __future__ import annotations

from pathlib import Path

import pytest

from hermes_mission_control.config import MissionControlSettings
from hermes_mission_control.research_inbox import sync_research_inbox
from hermes_mission_control.research_upload import digest


class FakeResearchClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.bundles: list[dict] = []

    async def research_document_by_digest(self, content_digest: str):
        return self.documents.get(content_digest)

    async def register_research_bundle(self, payload: dict) -> dict:
        document = payload["document"] | {"id": "document-id"}
        self.documents[document["content_digest"]] = document
        self.bundles.append(payload)
        return {"document": document, "chunk_count": len(payload["chunks"])}


@pytest.mark.asyncio
async def test_inbox_adds_then_ignores_unchanged_book(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "research-methods.txt"
    source.write_text("Selection bias requires prospective controls.", encoding="utf-8")
    client = FakeResearchClient()

    first = await sync_research_inbox(settings, client)
    second = await sync_research_inbox(settings, client)

    assert first["counts"]["added"] == 1
    assert second["counts"]["unchanged"] == 1
    assert len(client.bundles) == 1
    document = client.bundles[0]["document"]
    assert document["document_type"] == "textbook"
    assert document["evidence_type"] == "method"
    assert document["metadata"]["domains"] == ["systematic-research"]
    assert document["content_digest"] == digest(source.read_bytes())


@pytest.mark.asyncio
async def test_inbox_rejects_symlink_without_reading_target(
    settings: MissionControlSettings, tmp_path: Path
) -> None:
    settings.prepare()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    link = settings.research_inbox / "papers" / "escape.pdf"
    link.symlink_to(outside)

    report = await sync_research_inbox(settings, FakeResearchClient())

    assert report["counts"]["rejected"] == 1
    assert report["files"][0]["error"] == "Inbox sources must be regular files."


@pytest.mark.asyncio
async def test_root_files_default_to_empirical_papers(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    (settings.research_inbox / "finding.md").write_text(
        "# Finding\nObserved evidence.", encoding="utf-8"
    )
    client = FakeResearchClient()

    report = await sync_research_inbox(settings, client)

    assert report["files"][0]["document_type"] == "paper"
    assert report["files"][0]["evidence_type"] == "empirical_evidence"


@pytest.mark.asyncio
async def test_imported_prior_results_are_explicitly_classified(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "imported-prior-results" / "legacy.md"
    source.write_text("# Legacy result\nRejected after costs.", encoding="utf-8")
    client = FakeResearchClient()

    report = await sync_research_inbox(settings, client)

    assert report["files"][0]["document_type"] == "prior_report"
    assert report["files"][0]["evidence_type"] == "prior_result"


@pytest.mark.asyncio
async def test_deprecated_prior_results_folder_is_rejected(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    legacy = settings.research_inbox / "prior-results"
    legacy.mkdir()
    (legacy / "result.md").write_text("Old ambiguous lane", encoding="utf-8")

    report = await sync_research_inbox(settings, FakeResearchClient())

    assert report["counts"]["rejected"] == 1
    assert "imported-prior-results" in report["files"][0]["error"]
