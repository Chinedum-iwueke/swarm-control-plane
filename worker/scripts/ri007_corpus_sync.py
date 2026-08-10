#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory legacy Hermes research records for RI-007 reconciliation."
    )
    parser.add_argument("action", choices=("inventory-legacy",))
    args = parser.parse_args()
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    path = {
        "inventory-legacy": "/v1/research/corpus-sync/legacy-hermes/inventory"
    }[args.action]
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    ) as client:
        response = client.post(path)
        response.raise_for_status()
        document = response.json()
    print(json.dumps(document, indent=2, sort_keys=True))
    return 1 if document["status"] == "attention_required" else 0


if __name__ == "__main__":
    raise SystemExit(main())
