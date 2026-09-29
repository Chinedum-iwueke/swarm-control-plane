from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ri017_external_acquisition.py"
SPEC = importlib.util.spec_from_file_location("ri017_external_acquisition", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def definition() -> dict:
    return {
        "project": "systematic-research",
        "source_key": "fixture-public-feed",
        "name": "Fixture Public Feed",
        "feed_url": "https://feed.example/research.xml",
        "feed_kind": "atom",
        "domains": ["finance"],
        "rights": "Public metadata only.",
        "access_class": "public",
        "cadence": "daily",
        "freshness_hours": 48,
        "owner": "canon-curator",
        "allowed_hosts": ["feed.example"],
        "is_enabled": True,
    }


def test_parse_syndication_rejects_unsafe_xml_and_non_https_entries() -> None:
    with pytest.raises(ValueError, match="unsafe XML"):
        MODULE.parse_syndication(b"<!DOCTYPE x><feed />", allowed_host="feed.example")
    document = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>one</id><title>Safe title</title><summary>Safe abstract</summary>
      <published>2026-09-29T00:00:00Z</published>
      <link href="https://papers.example/one" /></entry>
      <entry><id>two</id><title>Unsafe URL</title><summary>Not retained</summary>
      <published>2026-09-29T00:00:00Z</published>
      <link href="http://papers.example/two" /></entry>
    </feed>"""
    entries = MODULE.parse_syndication(document, allowed_host="feed.example")
    assert [item["external_id"] for item in entries] == ["one"]


def test_acquisition_registers_fetch_receipt_without_scientific_authority(
    tmp_path: Path,
) -> None:
    source = definition() | {"id": "11111111-1111-4111-8111-111111111111"}
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/sources"):
            return httpx.Response(201, json=source)
        return httpx.Response(
            201,
            json={
                "status": "succeeded",
                "new_count": 1,
                "duplicate_count": 0,
                "rejected_count": 0,
                "receipt_digest": "a" * 64,
            },
        )

    with httpx.Client(
        base_url="https://control.example",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = MODULE.acquire(
            api=client,
            definitions=[definition()],
            state_path=tmp_path / "state.json",
            fetcher=lambda _: (
                200,
                [
                    {
                        "external_id": "paper-1",
                        "title": "Predictive relation",
                        "abstract": "A public abstract.",
                        "canonical_url": "https://papers.example/1",
                        "published_at": "2026-09-29T00:00:00+00:00",
                        "updated_at": None,
                        "doi": None,
                        "authors": [],
                        "status": "published",
                        "corrects_external_id": None,
                        "retracts_external_id": None,
                    }
                ],
            ),
        )

    state = json.loads((tmp_path / "state.json").read_text())
    assert result["sources"][0]["new_count"] == 1
    assert state["authority"] == {
        "scientific": False,
        "execution": False,
        "capital": False,
        "canonical_admission": False,
    }
    assert any(request.url.path.endswith("/poll") for request in calls)


def test_registry_rejects_private_or_credentialed_sources(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            [
                definition()
                | {
                    "feed_url": "https://127.0.0.1/private",
                    "allowed_hosts": ["127.0.0.1"],
                    "access_class": "restricted",
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="public sources"):
        MODULE.load_registry([path])

