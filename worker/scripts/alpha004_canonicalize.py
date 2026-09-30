#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile overlapping ALPHA-004 weeks to one exact canonical mandate."
    )
    parser.add_argument("--mandate-id", required=True)
    parser.add_argument("--expected-mandate-digest", required=True)
    parser.add_argument("--actor", default="founder-operator")
    parser.add_argument(
        "--reason",
        default=(
            "Reconcile legacy overlapping weekly mandates while preserving explicit "
            "thematic children and immutable historical evidence."
        ),
    )
    args = parser.parse_args()
    if len(args.expected_mandate_digest) != 64:
        parser.error("--expected-mandate-digest must be a SHA-256 digest.")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers=headers,
        timeout=60,
    ) as client:
        response = client.post(
            f"/v1/research/alpha-discovery/mandates/{args.mandate_id}/canonicalize",
            json={
                "expected_mandate_digest": args.expected_mandate_digest,
                "actor": args.actor,
                "reason": args.reason,
            },
        )
        if response.is_error:
            raise RuntimeError(
                f"Canonical reconciliation failed ({response.status_code}): "
                f"{response.text}"
            )
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
