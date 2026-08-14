from __future__ import annotations

import argparse
import json
import os
import time

from app.api.routes.ingestion import _pipeline, _store
from app.db.session import SessionLocal
from app.schemas.ingestion import IngestionRecoveryCreate
from app.services.ingestion_recovery import (
    process_next_recovery,
    queue_recoveries,
    requeue_recoverable_outcomes,
    requeue_stale_recoveries,
)
from app.services.recovery_steward import finalize_recovered_inbox


def run(
    *,
    max_items: int,
    load_ceiling: float,
    poll_seconds: float,
    stale_after_seconds: int,
    queue_project: str | None,
    requested_by: str,
    continuous: bool = False,
    settle_seconds: int = 300,
) -> int:
    processed = 0
    dirty = False
    last_recovery_at = 0.0
    while continuous or processed < max_items:
        with SessionLocal() as db:
            if queue_project is not None:
                queued, existing, _ = queue_recoveries(
                    db,
                    IngestionRecoveryCreate(
                        schema_version="scientific-ingestion-recovery-v1.0.0",
                        project=queue_project,
                        requested_by=requested_by,
                        limit=max_items,
                    ),
                )
                if queued:
                    print(
                        json.dumps(
                            {
                                "event": "pdf_recoveries_queued",
                                "queued": queued,
                                "existing": existing,
                            }
                        ),
                        flush=True,
                    )
            requeued = requeue_stale_recoveries(
                db, stale_after_seconds=stale_after_seconds
            )
            retried = requeue_recoverable_outcomes(db)
        if requeued or retried:
            print(
                json.dumps(
                    {
                        "event": "pdf_recovery_claims_requeued",
                        "stale": requeued,
                        "recoverable": retried,
                    }
                ),
                flush=True,
            )
        if os.getloadavg()[0] > load_ceiling:
            time.sleep(poll_seconds)
            continue
        with SessionLocal() as db:
            recovery = process_next_recovery(db, _store(), _pipeline())
        if recovery is None:
            if dirty and time.monotonic() - last_recovery_at >= settle_seconds:
                with SessionLocal() as db:
                    result = finalize_recovered_inbox(db)
                print(json.dumps({"event": "recovery_corpus_finalized", **result}))
                dirty = False
            if not continuous:
                break
            time.sleep(poll_seconds)
            continue
        processed += 1
        dirty = dirty or recovery.status == "recovered"
        if recovery.status == "recovered":
            last_recovery_at = time.monotonic()
        print(
            json.dumps(
                {
                    "event": "pdf_recovery_complete",
                    "recovery_id": str(recovery.id),
                    "status": recovery.status,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        time.sleep(poll_seconds)
    print(json.dumps({"event": "pdf_recovery_worker_stopped", "processed": processed}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded inert-PDF recovery.")
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--load-ceiling", type=float, default=6.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--stale-after-seconds", type=int, default=21600)
    parser.add_argument("--queue-project")
    parser.add_argument("--requested-by", default="pdf-recovery-worker")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--settle-seconds", type=int, default=300)
    args = parser.parse_args()
    if (
        args.max_items < 1
        or args.poll_seconds < 1
        or args.load_ceiling <= 0
        or args.stale_after_seconds < 3600
        or args.settle_seconds < 30
    ):
        parser.error("worker bounds must be positive")
    return run(
        max_items=args.max_items,
        load_ceiling=args.load_ceiling,
        poll_seconds=args.poll_seconds,
        stale_after_seconds=args.stale_after_seconds,
        queue_project=args.queue_project,
        requested_by=args.requested_by,
        continuous=args.continuous,
        settle_seconds=args.settle_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
