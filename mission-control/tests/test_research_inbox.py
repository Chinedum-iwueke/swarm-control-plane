from __future__ import annotations

from pathlib import Path

import pytest

from hermes_mission_control.config import MissionControlSettings
from hermes_mission_control.research_inbox import sync_research_inbox
from hermes_mission_control.research_upload import digest


class FakeResearchClient:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.ingestions: list[dict] = []
        self.runs: list[dict] = []

    async def create_scientific_ingestion(self, payload: dict) -> dict:
        content_digest = payload["content_digest"]
        if content_digest in self.jobs:
            return self.jobs[content_digest]
        job = {
            "id": f"job-{len(self.jobs) + 1}",
            "status": "quarantined",
            "published_object_ids": [],
            "stage_report": {},
        }
        self.jobs[content_digest] = job
        self.ingestions.append(payload)
        return job

    async def process_scientific_ingestion(self, job_id: str) -> dict:
        job = next(item for item in self.jobs.values() if item["id"] == job_id)
        job.update(status="published", published_object_ids=["canonical-source"])
        return job

    async def reconcile_corpus(self, payload: dict) -> dict:
        self.runs.append(payload)
        counts: dict[str, int] = {}
        for item in payload["items"]:
            counts[item["disposition"]] = counts.get(item["disposition"], 0) + 1
        return {
            "id": f"run-{len(self.runs)}",
            "status": "complete",
            "counts": counts,
            "coverage_digest": "a" * 64,
        }

    async def rebuild_corpus_projections(self, project: str) -> dict:
        assert project == "systematic-research"
        return {"evidence": {"projection_corpus_digest": "b" * 64}}


@pytest.mark.asyncio
async def test_inbox_adds_then_reconciles_unchanged_book(
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
    assert len(client.ingestions) == 1
    ingestion = client.ingestions[0]
    assert ingestion["source"]["origin"].endswith("books/research-methods.txt")
    assert ingestion["content_digest"] == digest(source.read_bytes())
    assert client.runs[-1]["items"][0]["classification"] == {
        "document_type": "textbook",
        "evidence_type": "method",
    }
    assert second["coverage"]["digest"] == "a" * 64


@pytest.mark.asyncio
async def test_inbox_rejects_symlink_without_reading_target(
    settings: MissionControlSettings, tmp_path: Path
) -> None:
    settings.prepare()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    link = settings.research_inbox / "papers" / "escape.pdf"
    link.symlink_to(outside)

    client = FakeResearchClient()
    report = await sync_research_inbox(settings, client)

    assert report["counts"]["rejected"] == 1
    assert report["files"][0]["error"] == "Inbox sources must be regular files."
    assert client.runs[0]["items"][0]["disposition"] == "excluded"


@pytest.mark.asyncio
async def test_root_files_default_to_empirical_papers(settings) -> None:
    settings.prepare()
    (settings.research_inbox / "finding.md").write_text(
        "# Finding\nObserved evidence.", encoding="utf-8"
    )
    report = await sync_research_inbox(settings, FakeResearchClient())
    assert report["files"][0]["document_type"] == "paper"
    assert report["files"][0]["evidence_type"] == "empirical_evidence"


@pytest.mark.asyncio
async def test_imported_prior_results_are_explicitly_classified(settings) -> None:
    settings.prepare()
    source = settings.research_inbox / "imported-prior-results" / "legacy.md"
    source.write_text("# Legacy result\nRejected after costs.", encoding="utf-8")
    report = await sync_research_inbox(settings, FakeResearchClient())
    assert report["files"][0]["document_type"] == "prior_report"
    assert report["files"][0]["evidence_type"] == "prior_result"


@pytest.mark.asyncio
async def test_deprecated_prior_results_folder_is_excluded(settings) -> None:
    settings.prepare()
    legacy = settings.research_inbox / "prior-results"
    legacy.mkdir()
    (legacy / "result.md").write_text("Old ambiguous lane", encoding="utf-8")
    report = await sync_research_inbox(settings, FakeResearchClient())
    assert report["counts"]["rejected"] == 1
    assert "imported-prior-results" in report["files"][0]["error"]
