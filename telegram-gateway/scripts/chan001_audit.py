#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_telegram_gateway.store import HandoffStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the restricted founder-channel local evidence chain."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("/srv/invariance/swarm/telegram-gateway/gateway.sqlite3"),
    )
    args = parser.parse_args()
    store = HandoffStore(args.database)
    store.initialize()
    valid, event_count, head_digest = store.verify_security_event_chain()
    report = {
        "schema_version": "chan001-security-audit-v1.0.0",
        "valid": valid,
        "event_count": event_count,
        "event_counts": store.security_event_counts(),
        "head_digest": head_digest,
        "transcript_content_retained": False,
        "action_authority": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
