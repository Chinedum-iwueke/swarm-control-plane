#!/usr/bin/env python3
"""Fetch public allowlisted research feeds and submit immutable RI-006 receipts."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

CONNECTOR_VERSION = "ri017-public-syndication-v1.0.0"
MAX_BYTES = 2_000_000
MAX_ENTRIES = 100


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


def load_registry(paths: list[Path]) -> list[dict]:
    definitions: list[dict] = []
    keys: set[str] = set()
    for path in paths:
        items = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            raise TypeError(f"source registry must be a list: {path}")
        for item in items:
            key = item.get("source_key") if isinstance(item, dict) else None
            if not isinstance(key, str) or key in keys:
                raise ValueError(f"invalid or duplicate source key in {path}: {key}")
            _validate_source(item)
            keys.add(key)
            definitions.append(item)
    return definitions


def _validate_source(source: dict) -> None:
    parsed = urlparse(str(source.get("feed_url", "")))
    hosts = source.get("allowed_hosts")
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("RI-017 sources require an HTTPS feed URL")
    if not isinstance(hosts, list) or hosts != [parsed.hostname]:
        raise ValueError("RI-017 sources require one exact feed-host allowlist entry")
    if source.get("access_class") != "public":
        raise ValueError("RI-017 phase one permits only public sources")
    if source.get("is_enabled") is not True:
        raise ValueError("disabled definitions do not belong in the active registry")


def _reject_nonpublic_resolution(host: str) -> None:
    addresses = {
        item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    }
    if not addresses:
        raise ValueError("approved source did not resolve")
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise ValueError(f"approved source resolved outside public address space: {host}")


def _parse_time(value: str) -> datetime:
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _text(item: ET.Element, name: str) -> str:
    node = item.find(f"{{*}}{name}")
    return "" if node is None else " ".join("".join(node.itertext()).split())


def parse_syndication(content: bytes, *, allowed_host: str) -> list[dict]:
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("unsafe XML declaration")
    root = ET.fromstring(content)
    nodes = root.findall("{*}entry") or root.findall("./channel/item")
    entries: list[dict] = []
    for item in nodes[:MAX_ENTRIES]:
        link_node = item.find("{*}link")
        link = (
            ""
            if link_node is None
            else (link_node.get("href") or link_node.text or "")
        ).strip()
        parsed = urlparse(link)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        external_id = _text(item, "id") or _text(item, "guid") or link
        title = _text(item, "title")
        abstract = _text(item, "summary") or _text(item, "description")
        published = _text(item, "published") or _text(item, "pubDate")
        updated = _text(item, "updated")
        if not external_id or not title or not abstract or not published:
            continue
        authors = [
            " ".join("".join(node.itertext()).split())
            for node in item.findall("{*}author/{*}name")
        ]
        entries.append(
            {
                "external_id": external_id[:500],
                "title": title[:1000],
                "abstract": abstract[:50_000],
                "canonical_url": link,
                "published_at": _parse_time(published).isoformat(),
                "updated_at": _parse_time(updated).isoformat() if updated else None,
                "doi": None,
                "authors": [value[:300] for value in authors[:100] if value],
                "status": "published",
                "corrects_external_id": None,
                "retracts_external_id": None,
                "retrieved_from_host": allowed_host,
            }
        )
    return entries


def fetch_source(source: dict) -> tuple[int, list[dict]]:
    parsed = urlparse(source["feed_url"])
    host = parsed.hostname or ""
    _reject_nonpublic_resolution(host)
    with httpx.Client(
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "application/atom+xml, application/rss+xml"},
    ) as client:
        response = client.get(source["feed_url"])
    if len(response.content) > MAX_BYTES:
        raise ValueError("feed response exceeds the connector limit")
    if response.status_code >= 400:
        return response.status_code, []
    entries = parse_syndication(response.content, allowed_host=host)
    for entry in entries:
        entry.pop("retrieved_from_host")
    return response.status_code, entries


def _source_equal(remote: dict, local: dict) -> bool:
    keys = set(local)
    return {key: remote.get(key) for key in keys} == local


def acquire(
    *,
    api: httpx.Client,
    definitions: list[dict],
    state_path: Path,
    fetcher: Callable[[dict], tuple[int, list[dict]]] = fetch_source,
) -> dict:
    response = api.get("/v1/research/surveillance/sources")
    response.raise_for_status()
    remote = {item["source_key"]: item for item in response.json()}
    outcomes: list[dict] = []
    for source in definitions:
        known = remote.get(source["source_key"])
        if known is None:
            created = api.post("/v1/research/surveillance/sources", json=source)
            created.raise_for_status()
            known = created.json()
        elif not _source_equal(known, source):
            raise ValueError(f"immutable source drift: {source['source_key']}")
        status = 503
        entries: list[dict] = []
        error = None
        for attempt in range(3):
            try:
                status, entries = fetcher(source)
                if status < 500:
                    break
            except (httpx.HTTPError, OSError, ValueError) as exc:
                error = type(exc).__name__
                status, entries = 503, []
            if attempt < 2:
                time.sleep(2**attempt)
        submitted = api.post(
            f"/v1/research/surveillance/sources/{known['id']}/poll",
            json={
                "requested_by": "ri017-public-worker",
                "entries": entries,
                "connector_version": CONNECTOR_VERSION,
                "fetched_at": datetime.now(UTC).isoformat(),
                "http_status": status,
            },
        )
        submitted.raise_for_status()
        receipt = submitted.json()
        outcomes.append(
            {
                "source_key": source["source_key"],
                "status": receipt["status"],
                "new_count": receipt["new_count"],
                "duplicate_count": receipt["duplicate_count"],
                "rejected_count": receipt["rejected_count"],
                "receipt_digest": receipt["receipt_digest"],
                "connector_error": error,
            }
        )
    state = {
        "schema_version": "ri017-acquisition-state-v1.0.0",
        "completed_at": datetime.now(UTC).isoformat(),
        "sources": outcomes,
        "authority": {
            "scientific": False,
            "execution": False,
            "capital": False,
            "canonical_admission": False,
        },
    }
    atomic_json(state_path, state)
    return {"event": "ri017_external_acquisition_complete", **state}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", action="append", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--api-url-file", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    api_url = read_secret(args.api_url_file).rstrip("/").removesuffix("/v1")
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {read_secret(args.token_file)}"},
        timeout=60,
    ) as api:
        result = acquire(
            api=api,
            definitions=load_registry(args.registry),
            state_path=args.state,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
