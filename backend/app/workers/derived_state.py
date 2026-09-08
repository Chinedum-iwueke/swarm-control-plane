from __future__ import annotations

import argparse
import json
import time

from app.db.session import SessionLocal
from app.services.derived_state import reconcile_once


def run_once(requested_by: str) -> str:
    with SessionLocal() as db:
        run = reconcile_once(db, requested_by)
        result = {
            "event": "derived_state_reconciliation_complete",
            "outcome": run.state if run else "no_change",
            "run_id": str(run.id) if run else None,
            "source_epoch": run.source_epoch_target if run else None,
        }
        print(json.dumps(result, sort_keys=True), flush=True)
        return result["outcome"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--requested-by", default="derived-state-orchestrator")
    args = parser.parse_args()
    while True:
        try:
            run_once(args.requested_by)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "event": "derived_state_reconciliation_failed",
                        "error": type(exc).__name__,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if not args.continuous:
                raise
        if not args.continuous:
            return 0
        time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
