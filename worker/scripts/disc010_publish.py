#!/usr/bin/env python3
"""Publish complete local DISC-010 receipts to the canonical Hermes registry."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import httpx


def atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_secret(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"credential file is empty: {path}")
    return value


def receipt_files(output_root: Path) -> list[Path]:
    root = output_root.resolve(strict=True)
    return sorted(
        path
        for path in root.glob("*/receipt.json")
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
    )


def publish(
    *,
    client: httpx.Client,
    output_root: Path,
    state_path: Path,
) -> dict:
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {
            "schema_version": "disc010-publisher-state-v1.0.0",
            "registrations": {},
        }
    )
    if set(state) != {"schema_version", "registrations"} or state[
        "schema_version"
    ] != "disc010-publisher-state-v1.0.0":
        raise ValueError("DISC-010 publisher state is malformed")
    registrations = state["registrations"]
    remote = client.get("/v1/research/quantitative-receipts")
    remote.raise_for_status()
    registered = {
        item["receipt_digest"]: item["id"]
        for item in remote.json()
        if item.get("milestone") == "DISC-010"
    }
    published = 0
    recovered = 0
    skipped = 0
    for path in receipt_files(output_root):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        digest = receipt.get("receipt_digest")
        if (
            receipt.get("milestone") != "DISC-010"
            or receipt.get("producer")
            != "bt.institutional.ohlcv_surveillance.ohlcv_signal_surveillance_receipt"
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError(f"noncanonical DISC-010 receipt at {path}")
        if digest in registrations:
            skipped += 1
            continue
        if digest in registered:
            registrations[digest] = {
                "receipt_id": registered[digest],
                "path": str(path),
            }
            recovered += 1
            continue
        response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "disc010-vm1-publisher"},
        )
        response.raise_for_status()
        record = response.json()
        registrations[digest] = {
            "receipt_id": record["id"],
            "path": str(path),
        }
        published += 1
    atomic_json(state_path, state)
    return {
        "event": "disc010_publication_complete",
        "published": published,
        "recovered": recovered,
        "already_registered": skipped,
        "registered_total": len(registrations),
        "authority": "research_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--api-url-file", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    api_url = read_secret(args.api_url_file).rstrip("/").removesuffix("/v1")
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {read_secret(args.token_file)}"},
        timeout=60,
    ) as client:
        result = publish(client=client, output_root=args.output_root, state_path=args.state)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
