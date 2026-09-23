from __future__ import annotations

import argparse
import json
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.alpha_discovery import AlphaResearchMandate
from app.services.alpha_discovery import reconstruct_mandate_counters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mandate_id", type=UUID)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        mandate = db.scalar(
            select(AlphaResearchMandate)
            .where(AlphaResearchMandate.id == args.mandate_id)
            .with_for_update()
        )
        if mandate is None:
            raise RuntimeError("Alpha research mandate not found.")
        report = reconstruct_mandate_counters(
            db,
            mandate,
            actor=args.actor,
            reason=args.reason,
            apply=args.apply,
        )
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
