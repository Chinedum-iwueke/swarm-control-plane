from __future__ import annotations

import argparse
import json
import time

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.alpha_campaign import AlphaCampaign
from app.services.alpha_campaign import reconcile_campaign


def _error_detail(exc: Exception):
    return (
        exc.errors(include_input=False)
        if isinstance(exc, ValidationError)
        else str(exc)[:2000]
    )


def run_once() -> dict:
    with SessionLocal() as db:
        campaigns = db.scalars(
            select(AlphaCampaign)
            .where(AlphaCampaign.status == "running")
            .order_by(AlphaCampaign.created_at)
            .with_for_update(skip_locked=True)
        ).all()
        failures = []
        for campaign in campaigns:
            try:
                with db.begin_nested():
                    reconcile_campaign(db, campaign)
            except (
                HTTPException,
                KeyError,
                TypeError,
                ValidationError,
                ValueError,
            ) as exc:
                failure = {
                    "campaign_id": str(campaign.id),
                    "error": type(exc).__name__,
                    "detail": _error_detail(exc),
                }
                failures.append(failure)
                print(
                    json.dumps(
                        {"event": "alpha_campaign_reconciliation_failed", **failure},
                        sort_keys=True,
                    ),
                    flush=True,
                )
        db.commit()
        result = {
            "event": "alpha_campaign_reconciliation_complete",
            "active_campaigns": len(campaigns),
            "failed_campaigns": failures,
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
                        "detail": _error_detail(exc),
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
