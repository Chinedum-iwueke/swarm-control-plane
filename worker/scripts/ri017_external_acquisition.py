#!/usr/bin/env python3
"""Fetch public allowlisted research feeds and submit immutable RI-006 receipts."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

CONNECTOR_VERSION = "ri017-public-syndication-v1.2.0"
MAX_BYTES = 2_000_000
MAX_ENTRIES = 100
MAX_TRANSCRIPT_INDEX_BYTES = 3_000_000
MAX_TRANSCRIPT_BYTES = 500_000
MAX_TRANSCRIPT_TOTAL_BYTES = 10_000_000
MAX_TRANSCRIPTS = 50
MAX_SCHOLARLY_PAGES = 100
MAX_SCHOLARLY_INDEX_BYTES = 5_000_000
MAX_SCHOLARLY_TOTAL_BYTES = 20_000_000


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
            raise ValueError(
                f"approved source resolved outside public address space: {host}"
            )


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
    if node is None:
        node = item.find(f".//{{*}}{name}")
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
            "" if link_node is None else (link_node.get("href") or link_node.text or "")
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


class _TranscriptIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._preview_depth = 0
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "li" and "podcast-preview" in classes:
            self._preview_depth = 1
            return
        if self._preview_depth and tag == "li":
            self._preview_depth += 1
        if self._preview_depth and tag == "a":
            href = values.get("href")
            if href and href.startswith("/") and href not in self.links:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if self._preview_depth and tag == "li":
            self._preview_depth -= 1


class _TranscriptEpisodeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._info_depth = 0
        self._transcript_depth = 0
        self._capture: str | None = None
        self._transcript_started = False
        self._transcript_marker_open = False
        self._title_parts: list[str] = []
        self._byline_parts: list[str] = []
        self._date_parts: list[str] = []
        self._transcript_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "div" and "podcast-info" in classes:
            self._info_depth = 1
        elif self._info_depth and tag == "div":
            self._info_depth += 1
        if tag == "div" and "transcript" in classes and "tab-view" in classes:
            self._transcript_depth = 1
        elif self._transcript_depth and tag == "div":
            self._transcript_depth += 1
        if self._info_depth and tag in {"h1", "h4", "h5"}:
            self._capture = tag
        if self._transcript_depth and tag == "h3" and values.get("id") == "transcript":
            self._transcript_marker_open = True

    def handle_endtag(self, tag: str) -> None:
        if tag == self._capture:
            self._capture = None
        if tag == "h3" and self._transcript_marker_open:
            self._transcript_marker_open = False
            self._transcript_started = True
        if self._info_depth and tag == "div":
            self._info_depth -= 1
        if self._transcript_depth and tag == "div":
            self._transcript_depth -= 1
            if not self._transcript_depth:
                self._transcript_started = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        if self._capture == "h1":
            self._title_parts.append(value)
        elif self._capture == "h4":
            self._byline_parts.append(value)
        elif self._capture == "h5":
            self._date_parts.append(value)
        if self._transcript_started:
            self._transcript_parts.append(value)

    def entry(self, *, canonical_url: str) -> dict | None:
        title = " ".join(self._title_parts).strip()
        transcript = "\n".join(self._transcript_parts).strip()
        if not title or not transcript:
            return None
        raw_date = " ".join(self._date_parts)
        raw_date = raw_date.split("|")[-1].strip()
        raw_date = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", raw_date)
        try:
            published = datetime.strptime(raw_date, "%B %d, %Y").replace(tzinfo=UTC)
        except ValueError:
            return None
        byline = " ".join(self._byline_parts).strip()
        return {
            "external_id": canonical_url[:500],
            "title": title[:1000],
            "abstract": transcript[:50_000],
            "canonical_url": canonical_url,
            "published_at": published.isoformat(),
            "updated_at": None,
            "doi": None,
            "authors": [byline[:300]] if byline else [],
            "status": "published",
            "corrects_external_id": None,
            "retracts_external_id": None,
        }


class _ScholarlyIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        is_neurips = href.endswith("-Abstract-Conference.html")
        is_pmlr = bool(re.search(r"/v[0-9]+/[a-z0-9-]+\.html$", href))
        if (is_neurips or is_pmlr) and href not in self.links:
            self.links.append(href)


class _ScholarlyPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, list[str]] = {}
        self._abstract_depth = 0
        self._abstract_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "p" and "paper-abstract" in classes:
            self._abstract_depth = 1
            return
        if self._abstract_depth and tag == "p":
            self._abstract_depth += 1
        if tag != "meta":
            return
        name = (values.get("name") or values.get("property") or "").lower()
        content = " ".join((values.get("content") or "").split())
        if name and content:
            self.metadata.setdefault(name, []).append(content)

    def handle_endtag(self, tag: str) -> None:
        if self._abstract_depth and tag == "p":
            self._abstract_depth -= 1

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if self._abstract_depth and value:
            self._abstract_parts.append(value)

    def entry(self, *, canonical_url: str) -> dict | None:
        def first(*names: str) -> str:
            return next(
                (self.metadata[name][0] for name in names if self.metadata.get(name)),
                "",
            )

        title = first("citation_title", "og:title")
        abstract = first(
            "citation_abstract", "description", "og:description"
        ) or " ".join(self._abstract_parts)
        published = first(
            "citation_publication_date", "citation_date", "article:published_time"
        )
        if not title or not abstract or not published:
            return None
        try:
            published_at = _parse_time(published)
        except (TypeError, ValueError):
            year = re.search(r"(?:19|20)[0-9]{2}", published)
            if year is None:
                return None
            published_at = datetime(int(year.group()), 1, 1, tzinfo=UTC)
        return {
            "external_id": first("citation_doi") or canonical_url[:500],
            "title": title[:1000],
            "abstract": abstract[:50_000],
            "canonical_url": canonical_url,
            "published_at": published_at.isoformat(),
            "updated_at": None,
            "doi": (first("citation_doi") or None),
            "authors": self.metadata.get("citation_author", [])[:100],
            "status": "published",
            "corrects_external_id": None,
            "retracts_external_id": None,
        }


def _public_get(client: httpx.Client, url: str, *, max_bytes: int) -> httpx.Response:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("RI-017 retrieval requires an HTTPS URL")
    _reject_nonpublic_resolution(parsed.hostname)
    response = client.get(url)
    if len(response.content) > max_bytes:
        raise ValueError("source response exceeds the connector limit")
    return response


def fetch_transcript_index(source: dict) -> tuple[int, list[dict]]:
    base = source["feed_url"]
    allowed_host = source["allowed_hosts"][0]
    entries: list[dict] = []
    total_bytes = 0
    with httpx.Client(
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "text/html"},
    ) as client:
        index = _public_get(client, base, max_bytes=MAX_TRANSCRIPT_INDEX_BYTES)
        if index.status_code >= 400:
            return index.status_code, []
        parser = _TranscriptIndexParser()
        parser.feed(index.text)
        for path in parser.links[:MAX_TRANSCRIPTS]:
            url = urljoin(base, path)
            parsed = urlparse(url)
            if parsed.hostname != allowed_host:
                continue
            response = _public_get(client, url, max_bytes=MAX_TRANSCRIPT_BYTES)
            if response.status_code >= 400:
                continue
            total_bytes += len(response.content)
            if total_bytes > MAX_TRANSCRIPT_TOTAL_BYTES:
                break
            episode = _TranscriptEpisodeParser()
            episode.feed(response.text)
            entry = episode.entry(canonical_url=url)
            if entry is not None:
                entries.append(entry)
    return index.status_code, entries


def fetch_scholarly_index(source: dict) -> tuple[int, list[dict]]:
    base = source["feed_url"]
    allowed_host = source["allowed_hosts"][0]
    entries: list[dict] = []
    total_bytes = 0
    with httpx.Client(
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "text/html"},
    ) as client:
        index = _public_get(client, base, max_bytes=MAX_SCHOLARLY_INDEX_BYTES)
        if index.status_code >= 400:
            return index.status_code, []
        parser = _ScholarlyIndexParser()
        parser.feed(index.text)
        for path in parser.links[:MAX_SCHOLARLY_PAGES]:
            url = urljoin(base, path)
            if urlparse(url).hostname != allowed_host:
                continue
            response = _public_get(client, url, max_bytes=MAX_TRANSCRIPT_BYTES)
            if response.status_code >= 400:
                continue
            total_bytes += len(response.content)
            if total_bytes > MAX_SCHOLARLY_TOTAL_BYTES:
                break
            page = _ScholarlyPageParser()
            page.feed(response.text)
            entry = page.entry(canonical_url=url)
            if entry is not None:
                entries.append(entry)
    return index.status_code, entries


def fetch_public_social_search(source: dict) -> tuple[int, list[dict]]:
    with httpx.Client(
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "application/json"},
    ) as client:
        response = _public_get(client, source["feed_url"], max_bytes=MAX_BYTES)
    if response.status_code >= 400:
        return response.status_code, []
    document = response.json()
    posts = document.get("posts")
    if posts is None:
        posts = [item.get("post", {}) for item in document.get("feed", [])]
    entries = []
    for item in posts[:MAX_ENTRIES]:
        record = item.get("record", {})
        author = item.get("author", {})
        uri = str(item.get("uri", ""))
        text = " ".join(str(record.get("text", "")).split())
        created_at = record.get("createdAt")
        handle = str(author.get("handle", ""))
        rkey = uri.rsplit("/", 1)[-1]
        if not uri.startswith("at://") or not text or not created_at or not handle:
            continue
        entries.append(
            {
                "external_id": uri[:500],
                "title": text[:300],
                "abstract": text[:50_000],
                "canonical_url": f"https://bsky.app/profile/{handle}/post/{rkey}",
                "published_at": _parse_time(created_at).isoformat(),
                "updated_at": None,
                "doi": None,
                "authors": [handle[:300]],
                "status": "published",
                "corrects_external_id": None,
                "retracts_external_id": None,
            }
        )
    return response.status_code, entries


def fetch_source(source: dict) -> tuple[int, list[dict]]:
    if source["feed_kind"] == "html_transcript_index":
        return fetch_transcript_index(source)
    if source["feed_kind"] == "html_scholarly_index":
        return fetch_scholarly_index(source)
    if source["feed_kind"] == "public_social_search":
        return fetch_public_social_search(source)
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
                "entry_count": receipt["entry_count"],
                "new_count": receipt["new_count"],
                "duplicate_count": receipt["duplicate_count"],
                "rejected_count": receipt["rejected_count"],
                "receipt_digest": receipt["receipt_digest"],
                "connector_error": error,
            }
        )
    feed_kinds = sorted({source["feed_kind"] for source in definitions})
    channel_coverage = {
        kind: {
            "expected_source_count": sum(
                1 for source in definitions if source["feed_kind"] == kind
            ),
            "successful_receipt_count": sum(
                1
                for item, source in zip(outcomes, definitions, strict=True)
                if source["feed_kind"] == kind and item["status"] == "succeeded"
            ),
            "nonempty_receipt_count": sum(
                1
                for item, source in zip(outcomes, definitions, strict=True)
                if source["feed_kind"] == kind
                and item["status"] == "succeeded"
                and item["entry_count"] > 0
            ),
            "entry_count": sum(
                item["entry_count"]
                for item, source in zip(outcomes, definitions, strict=True)
                if source["feed_kind"] == kind and item["status"] == "succeeded"
            ),
        }
        for kind in feed_kinds
    }
    unproven_channels = [
        kind
        for kind, coverage in channel_coverage.items()
        if coverage["successful_receipt_count"] != coverage["expected_source_count"]
        or coverage["nonempty_receipt_count"] != coverage["expected_source_count"]
    ]
    state = {
        "schema_version": "ri017-acquisition-state-v1.1.0",
        "completed_at": datetime.now(UTC).isoformat(),
        "sources": outcomes,
        "channel_coverage": channel_coverage,
        "operational_qualification": {
            "status": "qualified" if not unproven_channels else "not_qualified",
            "unproven_channels": unproven_channels,
            "receipt_digests": sorted(
                item["receipt_digest"] for item in outcomes if item["receipt_digest"]
            ),
            "claim_boundary": (
                "Qualification proves bounded retrieval, parsing and immutable API "
                "receipts for configured public channels only. It does not prove "
                "scientific truth, full-paper ingestion, YouTube transcript fidelity, "
                "or trading authority."
            ),
        },
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
