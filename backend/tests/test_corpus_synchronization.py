from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.corpus_sync import CorpusSyncRunCreate
from app.services.corpus_sync import reconcile_corpus

DIGEST = "a" * 64


def payload(items: list[dict]) -> CorpusSyncRunCreate:
    return CorpusSyncRunCreate.model_validate(
        {
            "schema_version": "corpus-sync-v1.0.0",
            "project": "systematic-research",
            "source_kind": "founder_inbox",
            "source_root": "mission-control-inbox",
            "requested_by": "founder-mission-control",
            "items": items,
        }
    )


def item(locator: str = "papers/a.pdf", digest: str = DIGEST) -> dict:
    return {
        "source_locator": locator,
        "content_digest": digest,
        "classification": {"document_type": "paper"},
        "access_class": "internal",
        "disposition": "canonical",
        "ingestion_job_id": str(JOB.id),
    }


JOB = SimpleNamespace(
    id=uuid4(),
    project="systematic-research",
    content_digest=DIGEST,
    status="published",
    published_object_ids=[uuid4(), uuid4()],
)


class FakeDB:
    def __init__(self, scalar_results, scalar_rows=(), jobs=None):
        self.scalar_results = list(scalar_results)
        self.scalar_rows = list(scalar_rows)
        self.jobs = jobs or {JOB.id: JOB}
        self.added = []
        self.items = []
        self.committed = False

    def scalar(self, _statement):
        return self.scalar_results.pop(0)

    def scalars(self, _statement):
        rows = self.scalar_rows.pop(0) if self.scalar_rows else []
        return SimpleNamespace(all=lambda: rows)

    def get(self, _model, identifier):
        return self.jobs.get(identifier)

    def add(self, value):
        if value.id is None:
            value.id = uuid4()
        self.added.append(value)

    def add_all(self, values):
        for value in values:
            if value.id is None:
                value.id = uuid4()
        self.items.extend(values)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def refresh(self, value):
        if value.created_at is None:
            value.created_at = datetime.now(UTC)


def test_canonical_inventory_is_digest_bound() -> None:
    db = FakeDB([None, None])
    run = reconcile_corpus(db, payload([item()]))
    assert run.status == "complete"
    assert run.counts == {"canonical": 1}
    assert run.coverage_digest != run.inventory_digest
    assert db.items[0].canonical_object_ids == [
        str(value) for value in JOB.published_object_ids
    ]


def test_renamed_content_is_a_duplicate_not_reingested() -> None:
    previous = SimpleNamespace(id=uuid4())
    previous_item = SimpleNamespace(
        id=uuid4(),
        source_locator="papers/old.pdf",
        content_digest=DIGEST,
        disposition="canonical",
        ingestion_job_id=JOB.id,
        classification={"document_type": "paper"},
        access_class="internal",
        canonical_object_ids=[str(value) for value in JOB.published_object_ids],
    )
    db = FakeDB([None, previous], [[previous_item]])
    run = reconcile_corpus(db, payload([item("papers/renamed.pdf")]))
    assert run.counts == {"duplicate": 1, "superseded": 1}
    current = next(value for value in db.items if value.source_locator.endswith("renamed.pdf"))
    assert current.predecessor_item_id == previous_item.id


def test_missing_source_is_retained_as_superseded() -> None:
    previous = SimpleNamespace(id=uuid4())
    prior = SimpleNamespace(
        id=uuid4(), source_locator="books/gone.pdf", content_digest=DIGEST,
        disposition="canonical", ingestion_job_id=JOB.id,
        classification={"document_type": "textbook"}, access_class="restricted",
        canonical_object_ids=[str(JOB.published_object_ids[0])],
    )
    db = FakeDB([None, previous], [[prior]])
    run = reconcile_corpus(db, payload([]))
    assert run.counts == {"superseded": 1}
    assert "retained" in db.items[0].detail


def test_identical_inventory_is_idempotent() -> None:
    existing = SimpleNamespace(id=uuid4(), inventory_digest="f" * 64)
    db = FakeDB([existing])
    assert reconcile_corpus(db, payload([item()])) is existing
    assert db.added == []


def test_unpublished_item_cannot_claim_canonical_disposition() -> None:
    bad_job = SimpleNamespace(**{**JOB.__dict__, "status": "remediation_required"})
    db = FakeDB([None, None], jobs={JOB.id: bad_job})
    with pytest.raises(Exception, match="not published"):
        reconcile_corpus(db, payload([item()]))
    assert db.committed is False


def test_cross_project_ingestion_evidence_is_denied() -> None:
    other = SimpleNamespace(**{**JOB.__dict__, "project": "other-project"})
    db = FakeDB([None, None], jobs={JOB.id: other})
    with pytest.raises(Exception, match="does not match"):
        reconcile_corpus(db, payload([item()]))
    assert db.committed is False


def test_unknown_fields_and_unexplained_exclusions_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload([item() | {"command": "rm -rf /"}])
    with pytest.raises(ValidationError, match="reason"):
        payload(
            [{
                "source_locator": "unsupported.bin",
                "access_class": "internal",
                "disposition": "excluded",
            }]
        )
    with pytest.raises(ValidationError, match="safe logical"):
        payload([item("../outside.pdf")])


def test_migration_is_additive_and_receipts_are_append_only() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/4d8f1b2c6a70_add_corpus_sync_ledger.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "3c7e9a1d5b40"' in migration
    assert "corpus_sync_runs" in migration
    assert "corpus_sync_items" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "scientific_ingestion_jobs" in migration
