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
    requeue_stale_recoveries,
)


def run(
    *,
    max_items: int,
    load_ceiling: float,
    poll_seconds: float,
    stale_after_seconds: int,
    queue_project: str | None,
    requested_by: str,
) -> int:
    processed = 0
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
            print(
                json.dumps(
                    {
                        "event": "pdf_recoveries_queued",
                        "queued": queued,
                        "existing": existing,
                    }
                )
            )
        requeued = requeue_stale_recoveries(
            db, stale_after_seconds=stale_after_seconds
        )
    print(json.dumps({"event": "pdf_recovery_stale_claims_requeued", "count": requeued}))
    while processed < max_items:
        if os.getloadavg()[0] > load_ceiling:
            time.sleep(poll_seconds)
            continue
        with SessionLocal() as db:
            recovery = process_next_recovery(db, _store(), _pipeline())
        if recovery is None:
            break
        processed += 1
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
    args = parser.parse_args()
    if (
        args.max_items < 1
        or args.poll_seconds < 1
        or args.load_ceiling <= 0
        or args.stale_after_seconds < 3600
    ):
        parser.error("worker bounds must be positive")
    return run(
        max_items=args.max_items,
        load_ceiling=args.load_ceiling,
        poll_seconds=args.poll_seconds,
        stale_after_seconds=args.stale_after_seconds,
        queue_project=args.queue_project,
        requested_by=args.requested_by,
    )


if __name__ == "__main__":
    raise SystemExit(main())
