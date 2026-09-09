from __future__ import annotations

import argparse
import json
import time

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.alpha_campaign import AlphaCampaign
from app.services.alpha_campaign import reconcile_campaign


def run_once() -> dict:
    with SessionLocal() as db:
        campaigns = db.scalars(
            select(AlphaCampaign)
            .where(AlphaCampaign.status == "running")
            .order_by(AlphaCampaign.created_at)
            .with_for_update(skip_locked=True)
        ).all()
        for campaign in campaigns:
            reconcile_campaign(db, campaign)
        db.commit()
        result = {
            "event": "alpha_campaign_reconciliation_complete",
            "active_campaigns": len(campaigns),
            "campaigns": [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "phase": item.phase,
                    "next_action": item.next_action,
                    "hypotheses": item.hypothesis_count,
                    "trials": item.trial_count,
                }
                for item in campaigns
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
                        "event": "alpha_campaign_reconciliation_failed",
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
