import importlib.util
from pathlib import Path

import httpx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ri009b_curriculum_pilot.py"
SPEC = importlib.util.spec_from_file_location("ri009b_curriculum_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
diagnose = MODULE.diagnose
preflight = MODULE.preflight


def test_diagnostic_preserves_failed_target_and_unconfigured_domain() -> None:
    configured = {
        "id": "curriculum-1",
        "domain_key": "causal-reasoning",
        "version": "1.1.0",
    }
    unconfigured = {
        "id": "curriculum-2",
        "domain_key": "systematic-quantitative-research",
        "version": "1.0.0",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/research/curricula":
            return httpx.Response(200, json=[configured, unconfigured])
        if request.url.path.endswith("curriculum-1/evaluations"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "evaluation-1",
                        "passed": False,
                        "metrics": {"opposition_recall": 0.5},
                        "case_specifications": [
                            {
                                "case_key": "causal-opposition",
                                "opposition_query": "confounding limitation",
                                "opposing_object_ids": ["target-1"],
                            }
                        ],
                    }
                ],
            )
        if request.url.path.endswith("curriculum-2/evaluations"):
            return httpx.Response(200, json=[])
        if request.url.path == "/v1/research/retrieval/query":
            return httpx.Response(
                200,
                json={
                    "candidate_counts": {"bounded": 500},
                    "hits": [
                        {
                            "object_id": "competitor-1",
                            "confidence": 0.7,
                            "text": "A competing passage.",
                        }
                    ],
                },
            )
        if request.url.path.endswith("/objects/target-1"):
            return httpx.Response(
                200,
                json={
                    "content_digest": "a" * 64,
                    "payload": {
                        "content_text": "The independently pinned opposing passage.",
                        "coordinates": {"page": 4, "line_start": 2, "line_end": 3},
                    },
                },
            )
        raise AssertionError(request.url.path)

    catalog = {
        "project": "systematic-research",
        "domains": [{"key": "causal-reasoning"}],
    }
    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = diagnose(client, catalog)

    failure = result["failed_domains"][0]
    assert failure["domain_key"] == "causal-reasoning"
    assert failure["cases"][0]["targets"][0]["returned_rank"] is None
    assert failure["cases"][0]["targets"][0]["content_digest"] == "a" * 64
    assert result["registered_domains_absent_from_catalog"][0]["domain_key"] == (
        "systematic-quantitative-research"
    )


def test_preflight_is_read_only_and_requires_both_targets() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/research/retrieval/query":
            return httpx.Response(
                200,
                json={
                    "candidate_counts": {"bounded": 2},
                    "hits": [
                        {
                            "object_id": "expected-1",
                            "confidence": 0.8,
                            "text": "Expected passage.",
                        },
                        {
                            "object_id": "opposing-1",
                            "confidence": 0.7,
                            "text": "Opposing passage.",
                        },
                    ],
                },
            )
        object_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "content_digest": "b" * 64,
                "payload": {"content_text": f"Content for {object_id}."},
            },
        )

    catalog = {
        "version": "1.2.0",
        "project": "systematic-research",
        "domains": [
            {
                "key": "causal-reasoning",
                "held_out_query": "held out query",
                "opposing_query": "opposing query",
            }
        ],
    }
    anchors = {
        "domains": [
            {
                "key": "causal-reasoning",
                "expected_object_id": "expected-1",
                "opposing_object_id": "opposing-1",
            }
        ]
    }
    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = preflight(client, catalog, anchors)

    assert result["success"] is True
    assert result["domain_count"] == 1
    assert all(item["returned_rank"] for item in result["domains"][0]["checks"])
    assert all(method == "GET" for method, path in calls if "/objects/" in path)
    assert all(method == "POST" for method, path in calls if path.endswith("/query"))
