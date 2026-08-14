from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corpus_sync import CorpusSyncItem, CorpusSyncRun
from app.models.ingestion import ScientificIngestionJob, ScientificIngestionRecovery
from app.schemas.corpus_sync import CorpusSyncItemCreate, CorpusSyncRunCreate
from app.services.corpus_sync import reconcile_corpus
from app.services.graph import build_graph_projection
from app.services.retrieval import build_projections


def finalize_recovered_inbox(db: Session) -> dict:
    latest = db.scalar(
        select(CorpusSyncRun)
        .where(CorpusSyncRun.source_kind == "founder_inbox")
        .order_by(CorpusSyncRun.created_at.desc())
    )
    if latest is None:
        return {"status": "no_inbox_inventory", "mapped_recoveries": 0}
    items = list(
        db.scalars(
            select(CorpusSyncItem)
            .where(CorpusSyncItem.run_id == latest.id)
            .order_by(CorpusSyncItem.source_locator)
        )
    )
    recoveries = {
        row.original_job_id: row
        for row in db.scalars(
            select(ScientificIngestionRecovery).where(
                ScientificIngestionRecovery.status == "recovered"
            )
        )
    }
    proposed: list[CorpusSyncItemCreate] = []
    mapped = 0
    for item in items:
        job = db.get(ScientificIngestionJob, item.ingestion_job_id)
        disposition = item.disposition
        detail = item.detail
        recovery = recoveries.get(item.ingestion_job_id)
        if recovery is not None and recovery.sanitized_job_id is not None:
            recovered = db.get(ScientificIngestionJob, recovery.sanitized_job_id)
            if recovered is not None and recovered.status == "published":
                job = recovered
                if item.disposition == "quarantined":
                    mapped += 1
                disposition = "canonical"
                detail = "Canonical inert recovered edition; original quarantine evidence retained."
        proposed.append(
            CorpusSyncItemCreate(
                source_locator=item.source_locator,
                content_digest=job.content_digest if job else item.content_digest,
                classification={
                    str(key): str(value) for key, value in item.classification.items()
                },
                access_class=item.access_class,
                disposition=disposition,
                ingestion_job_id=job.id if job else item.ingestion_job_id,
                detail=detail,
            )
        )
    if mapped == 0:
        return {"status": "unchanged", "mapped_recoveries": 0}
    run = reconcile_corpus(
        db,
        CorpusSyncRunCreate(
            schema_version="corpus-sync-v1.0.0",
            project=latest.project,
            source_kind="founder_inbox",
            source_root=latest.source_root,
            requested_by="recovery-steward",
            items=proposed,
        ),
    )
    retrieval = build_projections(db)
    graph = build_graph_projection(db)
    return {
        "status": run.status,
        "run_id": str(run.id),
        "counts": run.counts,
        "mapped_recoveries": mapped,
        "retrieval_digest": retrieval.corpus_digest,
        "retrieval_objects": retrieval.object_count,
        "graph_digest": graph.corpus_digest,
        "graph_nodes": graph.node_count,
        "graph_edges": graph.edge_count,
    }
