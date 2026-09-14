from __future__ import annotations

import argparse
import json
import time

from app.db.session import SessionLocal
from app.services.alpha_discovery import reconcile_all


def run_once() -> dict:
    with SessionLocal() as db:
        mandates = reconcile_all(db)
        db.commit()
        result = {
            "event": "alpha_discovery_reconciliation_complete",
            "active_mandates": len(mandates),
            "mandates": [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "cycles": item.cycle_count,
                    "hypotheses": item.hypothesis_count,
                    "trials": item.trial_count,
                }
                for item in mandates
            ],
        }
        print(json.dumps(result, sort_keys=True), flush=True)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    args = parser.parse_args()
    while True:
        try:
            run_once()
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "event": "alpha_discovery_reconciliation_failed",
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
