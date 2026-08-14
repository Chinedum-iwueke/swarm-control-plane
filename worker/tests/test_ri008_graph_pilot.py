import importlib.util
from pathlib import Path

import httpx

SCRIPT = Path(__file__).parents[1] / "scripts" / "ri008_graph_pilot.py"
SPEC = importlib.util.spec_from_file_location("ri008_graph_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def response(path: str, *, stale: bool = False) -> dict:
    if path.endswith(("/projections/status", "/rebuild")):
        return {
            "projection_name": "canonical-knowledge-graph",
            "projection_version": "knowledge-graph-v1.0.0",
            "corpus_digest": "a" * 64,
            "node_count": 2,
            "edge_count": 1,
            "manifest_digest": "b" * 64,
            "built_at": "2026-08-14T10:14:22Z",
            "stale": stale,
        }
    if path.endswith("/overview"):
        return {
            "query_digest": "c" * 64,
            "nodes": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "content_digest": "d" * 64,
                    "replay_path": (
                        "/v1/research/evidence/objects/"
                        "11111111-1111-4111-8111-111111111111"
                    ),
                }
            ],
            "edges": [],
            "truncated": False,
        }
    if path.endswith("/tools/execute"):
        return {
            "receipt_id": "22222222-2222-4222-8222-222222222222",
            "receipt_digest": "e" * 64,
            "result": {"value": 2.0},
        }
    return {"content_digest": "d" * 64}


def run_with_transport(*, stale: bool) -> tuple[dict, list[tuple[str, str]]]:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(
            200,
            json=response(request.url.path, stale=stale),
            request=request,
        )

    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = pilot.run_pilot(client)
    return result, requests


def test_current_projection_is_reused_without_rebuild() -> None:
    result, requests = run_with_transport(stale=False)

    assert result["projection_rebuilt"] is False
    assert ("POST", "/v1/research/graph/projections/rebuild") not in requests
    assert result["sampled_replay_object_ids"] == [
        "11111111-1111-4111-8111-111111111111"
    ]


def test_stale_projection_is_rebuilt() -> None:
    result, requests = run_with_transport(stale=True)

    assert result["projection_rebuilt"] is True
    assert requests.count(("POST", "/v1/research/graph/projections/rebuild")) == 1


def test_missing_projection_is_rebuilt() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        status = 409 if request.url.path.endswith("/projections/status") else 200
        return httpx.Response(
            status,
            json=response(request.url.path),
            request=request,
        )

    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = pilot.run_pilot(client)

    assert result["projection_rebuilt"] is True
    assert ("POST", "/v1/research/graph/projections/rebuild") in requests
