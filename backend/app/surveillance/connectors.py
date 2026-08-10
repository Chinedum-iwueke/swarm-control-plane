from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

import httpx

from app.schemas.surveillance import FeedEntry


class FeedConnector(Protocol):
    version: str

    async def fetch(
        self, url: str, allowed_hosts: frozenset[str]
    ) -> tuple[int, list[FeedEntry]]: ...


class HttpSyndicationConnector:
    version = "http-syndication-v1.0.0"

    def __init__(
        self, *, timeout_seconds: float = 20, max_bytes: int = 2_000_000
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(
        self, url: str, allowed_hosts: frozenset[str]
    ) -> tuple[int, list[FeedEntry]]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError("feed URL is outside the approved HTTPS host allowlist")
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=False
        ) as client:
            response = await client.get(
                url, headers={"Accept": "application/atom+xml, application/rss+xml"}
            )
        content = response.content
        if len(content) > self._max_bytes:
            raise ValueError("feed response exceeds the connector limit")
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ValueError("feed XML declarations are unsafe")
        if response.status_code >= 400:
            return response.status_code, []
        return response.status_code, parse_syndication(content)


def parse_syndication(content: bytes) -> list[FeedEntry]:
    root = ET.fromstring(content)
    entries = root.findall("{*}entry") or root.findall("./channel/item")
    result: list[FeedEntry] = []
    for item in entries[:500]:
        link_node = item.find("{*}link")
        link = (
            "" if link_node is None else (link_node.get("href") or link_node.text or "")
        )
        external_id = _text(item, "id") or _text(item, "guid") or link
        published = _text(item, "published") or _text(item, "pubDate")
        updated = _text(item, "updated")
        result.append(
            FeedEntry(
                external_id=external_id,
                title=_text(item, "title"),
                abstract=_text(item, "summary") or _text(item, "description"),
                canonical_url=link,
                published_at=datetime.fromisoformat(published.replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if updated
                else None,
                authors=[
                    node.text.strip()
                    for node in item.findall("{*}author/{*}name")
                    if node.text
                ],
            )
        )
    return result


def _text(item: ET.Element, name: str) -> str:
    node = item.find(f"{{*}}{name}")
    return "" if node is None or node.text is None else " ".join(node.text.split())
