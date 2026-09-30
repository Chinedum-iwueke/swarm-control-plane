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


def test_official_transcript_parser_retains_only_episode_transcript() -> None:
    index = MODULE._TranscriptIndexParser()
    index.feed(
        '<a href="/not-an-episode/">outside</a>'
        '<li class="podcast-preview"><h2><a href="/episode-one/">One</a></h2>'
        '<a href="/episode-one/">duplicate</a></li>'
    )
    assert index.links == ["/episode-one/"]

    episode = MODULE._TranscriptEpisodeParser()
    episode.feed(
        '<div class="podcast-info episodes-10-and-beyond">'
        "<h1>Point-in-Time Data</h1><h4>with Researcher</h4>"
        "<h5>Episode 4 | September 2nd, 2026</h5></div>"
        '<div class="tab-view transcript episodes-28-and-beyond">'
        '<h3 id="summary">SUMMARY</h3><p>Not retained.</p>'
        '<h3 class="transcript-section" id="transcript">TRANSCRIPT</h3>'
        "<h1>Host</h1><p>Use only information available at decision time.</p>"
        "</div><footer>Not retained either.</footer>"
    )
    entry = episode.entry(canonical_url="https://signalsandthreads.com/episode-one/")
    assert entry is not None
    assert entry["title"] == "Point-in-Time Data"
    assert entry["authors"] == ["with Researcher"]
    assert entry["published_at"] == "2026-09-02T00:00:00+00:00"
    assert entry["abstract"] == "Host\nUse only information available at decision time."


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
                "entry_count": 1,
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
    assert state["schema_version"] == "ri017-acquisition-state-v1.1.0"
    assert result["sources"][0]["new_count"] == 1
    assert state["channel_coverage"]["atom"] == {
        "expected_source_count": 1,
        "successful_receipt_count": 1,
        "nonempty_receipt_count": 1,
        "entry_count": 1,
    }
    assert state["operational_qualification"]["status"] == "qualified"
    assert state["operational_qualification"]["receipt_digests"] == ["a" * 64]
    assert state["authority"] == {
        "scientific": False,
        "execution": False,
        "capital": False,
        "canonical_admission": False,
    }
    assert any(request.url.path.endswith("/poll") for request in calls)


def test_empty_channel_receipt_is_honestly_not_qualified(tmp_path: Path) -> None:
    source = definition() | {"id": "11111111-1111-4111-8111-111111111111"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[source])
        return httpx.Response(
            201,
            json={
                "status": "succeeded",
                "entry_count": 0,
                "new_count": 0,
                "duplicate_count": 0,
                "rejected_count": 0,
                "receipt_digest": "b" * 64,
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
            fetcher=lambda _: (200, []),
        )

    assert result["operational_qualification"]["status"] == "not_qualified"
    assert result["operational_qualification"]["unproven_channels"] == ["atom"]


def test_scholarly_proceedings_parser_retains_metadata_not_full_text() -> None:
    index = MODULE._ScholarlyIndexParser()
    index.feed(
        '<a href="/paper_files/paper/2025/hash/abc-Abstract-Conference.html">Paper</a>'
        '<a href="/paper_files/paper/2025/file/abc-Paper-Conference.pdf">PDF</a>'
    )
    assert index.links == ["/paper_files/paper/2025/hash/abc-Abstract-Conference.html"]
    page = MODULE._ScholarlyPageParser()
    page.feed(
        '<meta name="citation_title" content="Causal market representation">'
        '<meta name="citation_author" content="Ada Researcher">'
        '<meta name="citation_publication_date" content="2025">'
        '<p class="paper-abstract"><p>We evaluate a frozen predictor.</p></p>'
    )
    entry = page.entry(canonical_url="https://proceedings.neurips.cc/paper")
    assert entry is not None
    assert entry["title"] == "Causal market representation"
    assert entry["authors"] == ["Ada Researcher"]
    assert entry["published_at"] == "2025-01-01T00:00:00+00:00"


def test_public_social_parser_marks_only_replayable_public_posts(monkeypatch) -> None:
    source = definition() | {
        "feed_url": "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=quant",
        "feed_kind": "public_social_search",
        "allowed_hosts": ["public.api.bsky.app"],
    }
    response = httpx.Response(
        200,
        request=httpx.Request("GET", source["feed_url"]),
        json={
            "posts": [
                {
                    "uri": "at://did:plc:abc/app.bsky.feed.post/xyz",
                    "author": {"handle": "research.example"},
                    "record": {
                        "text": "A public market observation, not scientific evidence.",
                        "createdAt": "2026-09-29T00:00:00Z",
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(MODULE, "_public_get", lambda *args, **kwargs: response)
    status, entries = MODULE.fetch_public_social_search(source)
    assert status == 200
    assert entries[0]["external_id"].startswith("at://")
    assert entries[0]["canonical_url"].startswith("https://bsky.app/")


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
