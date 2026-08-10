from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.surveillance import SurveillanceSource
from app.schemas.surveillance import SurveillanceSourceCreate, WeeklyDigestCreate
from app.services.surveillance import create_weekly_digest, poll_source, register_source
from app.surveillance.connectors import HttpSyndicationConnector
from app.surveillance.scheduler import SurveillanceScheduler


async def run_once() -> dict:
    registry = Path(__file__).with_name("approved_sources_v1.json")
    definitions = [
        SurveillanceSourceCreate.model_validate(item)
        for item in json.loads(registry.read_text(encoding="utf-8"))
    ]
    connector = HttpSyndicationConnector()
    scheduler = SurveillanceScheduler(connector)
    outcomes: list[dict] = []
    with SessionLocal() as db:
        for definition in definitions:
            source = register_source(db, definition)

            async def submit(payload, source_id=source.id):
                return poll_source(db, source_id, payload)

            receipt = await scheduler.collect(
                source, submit, requested_by="surveillance-scheduler"
            )
            outcomes.append(
                {
                    "source_key": source.source_key,
                    "status": receipt.status,
                    "new_count": receipt.new_count,
                    "duplicate_count": receipt.duplicate_count,
                    "rejected_count": receipt.rejected_count,
                    "receipt_digest": receipt.receipt_digest,
                }
            )
        enabled = db.scalar(
            select(SurveillanceSource.id).where(SurveillanceSource.is_enabled.is_(True))
        )
        if enabled is None:
            raise RuntimeError("no approved surveillance source is enabled")
        digest = create_weekly_digest(
            db,
            WeeklyDigestCreate(
                project="systematic-research",
                week_ending=datetime.now(UTC),
                requested_by="surveillance-scheduler",
            ),
        )
    return {
        "event": "surveillance_cycle_complete",
        "sources": outcomes,
        "weekly_digest_sha256": digest.digest_sha256,
        "candidate_count": digest.candidate_count,
    }


def main() -> int:
    print(json.dumps(asyncio.run(run_once()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
