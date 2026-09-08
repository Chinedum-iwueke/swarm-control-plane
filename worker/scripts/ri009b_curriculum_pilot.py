from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


def call(
    client: httpx.Client,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def trace_sources(
    client: httpx.Client,
    object_ids: list[str],
    cache: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    def evidence(object_id: str) -> dict[str, Any]:
        if object_id not in cache:
            cache[object_id] = call(
                client, "GET", f"/v1/research/evidence/objects/{object_id}"
            )
        return cache[object_id]

    traced: dict[str, list[str]] = {}
    for object_id in object_ids:
        scientific = evidence(object_id)
        artifact_id = scientific["payload"].get("artifact_object_id")
        artifact = evidence(artifact_id) if artifact_id else None
        edition_id = artifact["payload"].get("edition_object_id") if artifact else None
        edition = evidence(edition_id) if edition_id else None
        source_id = edition["payload"].get("source_object_id") if edition else None
        traced[object_id] = [source_id] if source_id else []
    return traced


def retrieve_candidates(
    client: httpx.Client,
    query: str,
    project: str,
    cache: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = call(
        client,
        "POST",
        "/v1/research/retrieval/query",
        {"query": query, "project": project, "limit": 8},
    )
    source_map = trace_sources(
        client,
        [str(hit["object_id"]) for hit in result["hits"]],
        cache,
    )
    candidates = []
    for hit in result["hits"]:
        sources = source_map[str(hit["object_id"])]
        if sources:
            candidates.append(
                {
                    "object_id": str(hit["object_id"]),
                    "source_ids": sources,
                    "confidence": hit["confidence"],
                    "excerpt": " ".join(hit["text"].split())[:300],
                }
            )
    return candidates


def discover(client: httpx.Client, catalog: dict[str, Any]) -> dict[str, Any]:
    project = catalog["project"]
    cache: dict[str, dict[str, Any]] = {}
    domains = []
    for domain in catalog["domains"]:
        domains.append(
            {
                "key": domain["key"],
                "supporting": retrieve_candidates(
                    client, domain["supporting_query"], project, cache
                ),
                "opposing": retrieve_candidates(
                    client, domain["opposing_query"], project, cache
                ),
                "held_out": retrieve_candidates(
                    client, domain["held_out_query"], project, cache
                ),
            }
        )
    return {"portfolio_key": catalog["portfolio_key"], "domains": domains}


def indexed_domains(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    domains = document["domains"]
    indexed = {item["key"]: item for item in domains}
    if len(indexed) != len(domains):
        raise ValueError("domain keys must be unique")
    return indexed


def prepare(
    client: httpx.Client,
    catalog: dict[str, Any],
    anchors: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog_domains = indexed_domains(catalog)
    anchor_domains = indexed_domains(anchors)
    if set(catalog_domains) != set(anchor_domains):
        raise ValueError("catalog and anchor domains do not match")

    curricula = []
    for domain_key in sorted(catalog_domains):
        domain = catalog_domains[domain_key]
        anchor = anchor_domains[domain_key]
        source_ids = sorted(
            {anchor["expected_source_id"], anchor["opposing_source_id"]}
        )
        if len(source_ids) != 2:
            raise ValueError(f"{domain_key} requires two distinct sources")
        curricula.append(
            call(
                client,
                "POST",
                "/v1/research/curricula",
                {
                    "domain_key": domain_key,
                    "version": catalog["version"],
                    "title": domain["title"],
                    "description": (
                        "Research Bible domain curriculum grounded in two "
                        "canonical, replayable evidence sources and evaluated "
                        "with held-out support, opposition, and abstention cases."
                    ),
                    "project": catalog["project"],
                    "topics": [
                        {
                            "key": domain["topic"],
                            "title": domain["title"],
                            "evidence_object_ids": [anchor["expected_object_id"]],
                            "source_object_ids": source_ids,
                            "opposing_evidence_object_ids": [
                                anchor["opposing_object_id"]
                            ],
                            "minimum_sources": 2,
                        }
                    ],
                    "source_quality": {
                        "allowed_authority_classes": [
                            "primary",
                            "derived",
                            "institutional",
                            "operational",
                        ],
                        "minimum_distinct_sources_per_topic": 2,
                        "maximum_quarantined_fraction": 0.05,
                        "require_opposing_evidence": True,
                    },
                    "qualified_roles": catalog["qualified_roles"],
                    "review_cadence_days": 90,
                    "created_by": "ri009b-curriculum-evaluator",
                },
            )
        )
    return curricula


def evaluate(
    client: httpx.Client,
    catalog: dict[str, Any],
    anchors: dict[str, Any],
    curricula: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    catalog_domains = indexed_domains(catalog)
    anchor_domains = indexed_domains(anchors)
    curriculum_domains = {item["domain_key"]: item for item in curricula}
    evaluations = []
    for domain_key in sorted(catalog_domains):
        domain = catalog_domains[domain_key]
        anchor = anchor_domains[domain_key]
        curriculum = curriculum_domains[domain_key]
        payload = {
            "curriculum_id": curriculum["id"],
            "evaluation_version": catalog.get(
                "evaluation_version", catalog["version"]
            ),
            "cases": [
                {
                    "case_key": f"{domain_key}-held-out",
                    "query": domain["held_out_query"],
                    "opposition_query": domain["opposing_query"],
                    "expected_object_ids": [anchor["expected_object_id"]],
                    "opposing_object_ids": [anchor["opposing_object_id"]],
                },
                {
                    "case_key": f"{domain_key}-unknown",
                    "query": (
                        "What was the result of private study "
                        f"HERMES-RI009B-{domain_key.upper()}-ZQX-2049?"
                    ),
                    "should_abstain": True,
                },
            ],
            "thresholds": {
                "minimum_retrieval_recall": 1.0,
                "minimum_citation_fidelity": 1.0,
                "minimum_opposition_recall": 1.0,
                "minimum_abstention_accuracy": 1.0,
                "maximum_cross_domain_leakage": 0.0,
                "minimum_topic_coverage": 1.0,
            },
            "evaluated_by": "ri009b-independent-evaluator",
        }
        evaluations.append(
            call(
                client,
                "POST",
                f"/v1/research/curricula/{curriculum['id']}/evaluations",
                payload,
            )
        )
    return evaluations


def finalize(
    client: httpx.Client,
    catalog: dict[str, Any],
    curricula: list[dict[str, Any]],
) -> dict[str, Any]:
    curricula_by_domain = {item["domain_key"]: item for item in curricula}
    domain_keys = sorted(curricula_by_domain)
    return call(
        client,
        "POST",
        "/v1/research/curricula/portfolios",
        {
            "portfolio_key": catalog["portfolio_key"],
            "version": catalog.get("portfolio_version", catalog["version"]),
            "required_domain_keys": domain_keys,
            "curriculum_ids": [curricula_by_domain[key]["id"] for key in domain_keys],
            "created_by": "ri009b-independent-evaluator",
        },
    )


def load_document(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("discover", "all"))
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("worker/curricula/ri009b-research-bible.yaml"),
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        default=Path("worker/curricula/ri009b-live-anchors.yaml"),
    )
    parser.add_argument("--version")
    parser.add_argument("--evaluation-version")
    parser.add_argument("--portfolio-version")
    args = parser.parse_args()
    catalog = load_document(args.catalog)
    if args.version:
        catalog["version"] = args.version
    if args.evaluation_version:
        catalog["evaluation_version"] = args.evaluation_version
    if args.portfolio_version:
        catalog["portfolio_version"] = args.portfolio_version
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={
            "Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
        },
        timeout=300,
    ) as client:
        if args.command == "discover":
            result = discover(client, catalog)
        else:
            anchors = load_document(args.anchors)
            curricula = prepare(client, catalog, anchors)
            evaluations = evaluate(client, catalog, anchors, curricula)
            portfolio = finalize(client, catalog, curricula)
            result = {
                "portfolio": portfolio,
                "curricula": [
                    {
                        "domain_key": item["domain_key"],
                        "id": item["id"],
                        "record_digest": item["record_digest"],
                    }
                    for item in curricula
                ],
                "evaluations": [
                    {
                        "curriculum_id": item["curriculum_id"],
                        "id": item["id"],
                        "passed": item["passed"],
                        "record_digest": item["record_digest"],
                    }
                    for item in evaluations
                ],
            }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "all" and not result["portfolio"]["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
