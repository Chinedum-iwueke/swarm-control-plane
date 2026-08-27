#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DISC-009 live attention-allocation pilot."
    )
    parser.add_argument("--output", type=Path, default=Path("/tmp/disc009-report.json"))
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=120) as client:
        maps = (
            client.get(
                "/v1/research/discovery-maps", params={"status": "active", "limit": 100}
            )
            .raise_for_status()
            .json()
        )
        sessions = (
            client.get("/v1/research/autonomous-sessions").raise_for_status().json()
        )
        audits = client.get("/v1/research/selection-audits").raise_for_status().json()
        evaluations = (
            client.get("/v1/research/falsification/evaluations")
            .raise_for_status()
            .json()
        )
        plans = client.get("/v1/research/falsification/plans").raise_for_status().json()
        evaluations_by_id = {item["id"]: item for item in evaluations}
        plans_by_id = {item["id"]: item for item in plans}
        maps_by_id = {item["id"]: item for item in maps}
        completed = [item for item in sessions if item["status"] == "completed"]
        candidates = []
        for item in maps[:4]:
            candidates.append(
                {
                    "candidate_key": f"map-{item['id'][:8]}",
                    "domain_key": f"discovery-{item['stage']}",
                    "cluster_key": f"map-{item['stage']}",
                    "source_type": "discovery_map",
                    "source_id": item["id"],
                    "source_digest": item["map_digest"],
                    "question": item["document"]["question"],
                    "decision_relevance": 0.8,
                    "feasibility": 0.75,
                    "attention_cost": 1,
                }
            )
        for item in completed[:2]:
            candidates.append(
                {
                    "candidate_key": f"session-{item['id'][:8]}",
                    "domain_key": "autonomous-research",
                    "cluster_key": "retained-session-outcomes",
                    "source_type": "autonomous_session",
                    "source_id": item["id"],
                    "source_digest": item["closeout"]["closeout_digest"],
                    "question": item["objective"],
                    "decision_relevance": 0.7,
                    "feasibility": 0.9,
                    "attention_cost": 1,
                }
            )
        for item in [record for record in audits if record["status"] == "active"][:2]:
            evaluation = evaluations_by_id[item["mechanism_evaluation_id"]]
            plan = plans_by_id[evaluation["plan_id"]]
            discovery = maps_by_id[plan["discovery_map_id"]]
            candidates.append(
                {
                    "candidate_key": f"selection-{item['id'][:8]}",
                    "domain_key": "selection-bias",
                    "cluster_key": "selection-audit",
                    "source_type": "selection_bias_audit",
                    "source_id": item["id"],
                    "source_digest": item["audit_digest"],
                    "question": (
                        "How should the selection-bias conclusion alter confidence in: "
                        + discovery["document"]["question"]
                    ),
                    "decision_relevance": 0.9,
                    "feasibility": 0.8,
                    "attention_cost": 1,
                }
            )
        if len(candidates) < 3 or len({item["domain_key"] for item in candidates}) < 2:
            raise RuntimeError(
                "Live canonical sources cannot demonstrate diversified allocation."
            )
        payload = {
            "portfolio_key": "DISC009-LIVE-PORTFOLIO",
            "version": "1.0.0",
            "project": "bulletproof-bt",
            "objective": "Allocate the next bounded discovery attention across canonical uncertainty sources.",
            "source_epoch": datetime.now(UTC).isoformat(),
            "policy": {
                "attention_budget": 2,
                "maximum_selected": 2,
                "minimum_distinct_domains": 2,
                "maximum_per_domain": 1,
                "maximum_per_cluster": 1,
                "relevance_weight": 0.45,
                "feasibility_weight": 0.35,
                "novelty_weight": 0.2,
            },
            "candidates": candidates,
            "created_by": "disc009-pilot",
        }
        portfolios = (
            client.get("/v1/research/discovery-portfolios").raise_for_status().json()
        )
        portfolio = next(
            (
                item
                for item in portfolios
                if item["portfolio_key"] == payload["portfolio_key"]
                and item["version"] == payload["version"]
            ),
            None,
        )
        if portfolio is None:
            portfolio = (
                client.post("/v1/research/discovery-portfolios", json=payload)
                .raise_for_status()
                .json()
            )
        replay = (
            client.get(f"/v1/research/discovery-portfolios/{portfolio['id']}")
            .raise_for_status()
            .json()
        )
    selected = [item for item in portfolio["candidates"] if item["selected"]]
    rejected = [item for item in portfolio["candidates"] if not item["selected"]]
    report = {
        "schema_version": "disc009-pilot-report-v1.0.0",
        "portfolio_id": portfolio["id"],
        "portfolio_key": portfolio["portfolio_key"],
        "version": portfolio["version"],
        "allocation_digest": portfolio["allocation_digest"],
        "policy_digest": portfolio["policy_digest"],
        "candidate_count": portfolio["candidate_count"],
        "selected_count": portfolio["selected_count"],
        "attention_used": portfolio["attention_used"],
        "selected_domains": sorted({item["domain_key"] for item in selected}),
        "selected_candidate_digests": [item["candidate_digest"] for item in selected],
        "counterfactual_decisions": {
            item["candidate_key"]: item["decision"]["reason"] for item in rejected
        },
        "event_chain": [item["event_digest"] for item in portfolio["events"]],
        "exact_replay": replay["allocation_digest"] == portfolio["allocation_digest"],
        "task_creation_authority": False,
        "execution_authority": False,
        "promotion_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = digest(report)
    if (
        report["selected_count"] < 2
        or len(report["selected_domains"]) < 2
        or not report["counterfactual_decisions"]
        or not report["exact_replay"]
    ):
        raise RuntimeError(
            "DISC-009 live evidence did not satisfy the scheduler contract."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
