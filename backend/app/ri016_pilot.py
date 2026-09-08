from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.services.derived_state import (
    derived_state_status,
    execute_reconciliation,
    schedule_reconciliation,
)
from app.services.graph import graph_projection_content_digest
from app.services.retrieval import retrieval_projection_digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("reconcile", "parity"), default="reconcile", nargs="?"
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        before = derived_state_status(db)
        prior_digests = (
            {
                "retrieval": retrieval_projection_digest(db),
                "graph": graph_projection_content_digest(db),
            }
            if args.command == "parity"
            and not before["retrieval"]["stale"]
            and not before["graph"]["stale"]
            else None
        )
        run = schedule_reconciliation(
            db,
            requested_by="ri016-live-pilot",
            force_full=args.command == "parity",
        )
        if run is not None and run.state not in {"succeeded", "needs_attention"}:
            run = execute_reconciliation(db, run.id)
        after = derived_state_status(db)
        rebuilt_digests = (
            {
                "retrieval": retrieval_projection_digest(db),
                "graph": graph_projection_content_digest(db),
            }
            if prior_digests is not None
            else None
        )
        parity = prior_digests is None or prior_digests == rebuilt_digests
        report = {
            "schema_version": "ri016-pilot-report-v1.0.0",
            "command": args.command,
            "outcome": run.state if run is not None else "no_change",
            "run_id": str(run.id) if run is not None else None,
            "source_epoch": after["corpus_epoch"],
            "current": after["current"],
            "pending_changes": after["pending_changes"],
            "incremental_full_digest_parity": parity,
            "prior_digests": prior_digests,
            "rebuilt_digests": rebuilt_digests,
            "claim_boundary": after["claim_boundary"],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if parity and after["current"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
