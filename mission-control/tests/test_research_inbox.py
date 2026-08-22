from __future__ import annotations

import fcntl
import json
from pathlib import Path

import pytest

from hermes_mission_control import research_inbox
from hermes_mission_control.config import MissionControlSettings
from hermes_mission_control.research_inbox import (
    research_inbox_status,
    sync_research_inbox,
)
from hermes_mission_control.research_upload import ResearchUploadError, digest


class FakeResearchClient:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.ingestions: list[dict] = []
        self.runs: list[dict] = []
        self.projection_rebuilds = 0
        self.recoveries: dict[str, dict] = {}

    async def scientific_ingestion_by_digest(self, content_digest: str) -> dict | None:
        return self.jobs.get(content_digest)

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

    async def recovered_scientific_ingestion(self, job_id: str) -> dict | None:
        return self.recoveries.get(job_id)

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
        self.projection_rebuilds += 1
        return {"evidence": {"projection_corpus_digest": "b" * 64}}


class RetryResearchClient(FakeResearchClient):
    def __init__(self) -> None:
        super().__init__()
        self.process_calls = 0

    async def process_scientific_ingestion(self, job_id: str) -> dict:
        self.process_calls += 1
        job = next(item for item in self.jobs.values() if item["id"] == job_id)
        if self.process_calls == 1:
            return job
        job.update(status="published", published_object_ids=["recovered-source"])
        return job


@pytest.mark.asyncio
async def test_inbox_adds_then_reconciles_unchanged_book(
    settings: MissionControlSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "research-methods.txt"
    source.write_text("Selection bias requires prospective controls.", encoding="utf-8")
    client = FakeResearchClient()

    first = await sync_research_inbox(settings, client)
    monkeypatch.setattr(
        research_inbox,
        "digest",
        lambda _content: pytest.fail("unchanged file was rehashed"),
    )
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
    assert second["incremental"] == {
        "corpus_changed": False,
        "projection_rebuilt": False,
        "index": str(settings.research_inbox_index_path),
    }
    assert client.projection_rebuilds == 1


@pytest.mark.asyncio
async def test_inbox_renamed_canonical_file_reuses_digest_receipt(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    original = settings.research_inbox / "papers" / "original.txt"
    original.write_text("Prospective evidence.", encoding="utf-8")
    client = FakeResearchClient()

    await sync_research_inbox(settings, client)
    original.rename(settings.research_inbox / "papers" / "renamed.txt")
    report = await sync_research_inbox(settings, client)

    assert len(client.ingestions) == 1
    assert report["counts"]["unchanged"] == 1
    assert report["incremental"]["corpus_changed"] is False


@pytest.mark.asyncio
async def test_inbox_checkpoints_progress(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "papers" / "evidence.txt"
    source.write_text("Bounded evidence.", encoding="utf-8")

    await sync_research_inbox(settings, FakeResearchClient())

    index = settings.research_inbox_index_path.read_text(encoding="utf-8")
    assert '"status": "complete"' in index
    assert '"remaining": 0' in index
    assert settings.research_inbox_index_path.stat().st_mode & 0o077 == 0
    assert research_inbox_status(settings)["run"]["status"] == "complete"


@pytest.mark.asyncio
async def test_inbox_rejects_concurrent_refresh(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    with settings.research_inbox_lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(
            ResearchUploadError, match="research inbox refresh is already running"
        ):
            await sync_research_inbox(settings, FakeResearchClient())


@pytest.mark.asyncio
async def test_inbox_removal_reconciles_without_rebuilding_projection(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "papers" / "removed.txt"
    source.write_text("Retained canonical evidence.", encoding="utf-8")
    client = FakeResearchClient()
    await sync_research_inbox(settings, client)

    source.unlink()
    report = await sync_research_inbox(settings, client)

    assert client.runs[-1]["items"] == []
    assert client.projection_rebuilds == 1
    assert report["incremental"]["corpus_changed"] is False


@pytest.mark.asyncio
async def test_inbox_persisted_dirty_projection_survives_resume(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "papers" / "checkpointed.txt"
    source.write_text("Checkpoint before projection.", encoding="utf-8")
    client = FakeResearchClient()
    await sync_research_inbox(settings, client)
    state = json.loads(settings.research_inbox_index_path.read_text(encoding="utf-8"))
    state["projection_dirty"] = True
    settings.research_inbox_index_path.write_text(json.dumps(state), encoding="utf-8")

    report = await sync_research_inbox(settings, client)

    assert len(client.ingestions) == 1
    assert client.projection_rebuilds == 2
    assert report["incremental"]["projection_rebuilt"] is True


@pytest.mark.asyncio
async def test_inbox_retries_cached_noncanonical_entry(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "papers" / "recoverable.txt"
    source.write_text("Recoverable evidence.", encoding="utf-8")
    client = RetryResearchClient()

    first = await sync_research_inbox(settings, client)
    second = await sync_research_inbox(settings, client)

    assert first["counts"]["rejected"] == 1
    assert second["counts"]["added"] == 1
    assert client.process_calls == 2
    assert client.projection_rebuilds == 2


@pytest.mark.asyncio
async def test_cold_index_bootstrap_reuses_server_digest_without_upload(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "known.txt"
    source.write_text("Already canonical evidence.", encoding="utf-8")
    content_digest = digest(source.read_bytes())
    client = FakeResearchClient()
    client.jobs[content_digest] = {
        "id": "known-job",
        "status": "published",
        "published_object_ids": ["known-object"],
        "stage_report": {},
    }

    report = await sync_research_inbox(settings, client)

    assert client.ingestions == []
    assert report["counts"]["unchanged"] == 1


@pytest.mark.asyncio
async def test_finalize_only_reuses_complete_checkpoint_without_ingestion(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "complete.txt"
    source.write_text("Complete checkpoint.", encoding="utf-8")
    client = FakeResearchClient()
    await sync_research_inbox(settings, client)
    state = json.loads(settings.research_inbox_index_path.read_text(encoding="utf-8"))
    state["run"]["status"] = "running"
    state["projection_dirty"] = True
    settings.research_inbox_index_path.write_text(json.dumps(state), encoding="utf-8")

    report = await sync_research_inbox(settings, client, finalize_only=True)

    assert len(client.ingestions) == 1
    assert report["incremental"]["projection_rebuilt"] is True
    assert research_inbox_status(settings)["run"]["status"] == "complete"


@pytest.mark.asyncio
async def test_finalize_only_reconciles_published_recovery(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "recovered.pdf"
    source.write_bytes(b"%PDF original active edition")
    client = RetryResearchClient()

    first = await sync_research_inbox(settings, client)
    original = first["files"][0]
    client.recoveries[original["ingestion_job_id"]] = {
        "recovery": {"id": "recovery-1", "status": "recovered"},
        "sanitized_job": {
            "id": "sanitized-job-1",
            "content_digest": "c" * 64,
            "status": "published",
            "published_object_ids": ["sanitized-object-1"],
            "stage_report": {},
        },
    }

    report = await sync_research_inbox(settings, client, finalize_only=True)

    item = report["files"][0]
    assert report["counts"]["added"] == 1
    assert item["disposition"] == "canonical"
    assert item["content_digest"] == "c" * 64
    assert item["ingestion_job_id"] == "sanitized-job-1"
    assert item["original_content_digest"] == digest(source.read_bytes())
    assert item["original_ingestion_job_id"] == original["ingestion_job_id"]
    assert item["recovery_id"] == "recovery-1"
    assert client.runs[-1]["items"][0]["disposition"] == "canonical"


@pytest.mark.asyncio
async def test_finalize_only_rejects_changed_checkpoint(
    settings: MissionControlSettings,
) -> None:
    settings.prepare()
    source = settings.research_inbox / "books" / "changed.txt"
    source.write_text("Original checkpoint.", encoding="utf-8")
    client = FakeResearchClient()
    await sync_research_inbox(settings, client)
    source.write_text("Changed after checkpoint.", encoding="utf-8")

    with pytest.raises(ResearchUploadError, match="changed after checkpoint"):
        await sync_research_inbox(settings, client, finalize_only=True)


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
