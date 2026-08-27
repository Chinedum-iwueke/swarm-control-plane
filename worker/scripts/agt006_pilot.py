#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def post_idempotent(client: httpx.Client, path: str, payload: dict, lookup) -> dict:
    response = client.post(path, json=payload)
    if response.status_code == 409:
        return lookup()
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded AGT-006 routing pilot."
    )
    parser.add_argument(
        "--roles", type=Path, default=Path("/etc/invariance-swarm/m13-role-state.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/agt006/report.json"),
    )
    args = parser.parse_args()
    roles = json.loads(args.roles.read_text(encoding="utf-8"))["roles"]
    selected_roles = {
        "statistical": roles["statistical"],
        "adversarial": roles["adversarial"],
    }
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        profiles = {}
        for kind, role in selected_roles.items():
            payload = {
                "agent_id": role["agent_id"],
                "profile_version": "1.0.0",
                "review_kinds": [kind],
                "capabilities": [
                    f"{kind}-review" if kind == "statistical" else "adversarial-audit"
                ],
                "provider": "openai",
                "model_family": "codex",
                "context_group": f"agt006-{kind}-isolated-context",
                "registered_by": "founder-operator",
            }
            response = client.post("/v1/evaluator-routing/profiles", json=payload)
            if response.status_code == 409:
                available = (
                    client.get("/v1/evaluator-routing/profiles")
                    .raise_for_status()
                    .json()
                )
                profile = next(
                    item
                    for item in available
                    if item["agent_id"] == role["agent_id"]
                    and item["profile_version"] == "1.0.0"
                )
            else:
                response.raise_for_status()
                profile = response.json()
            profiles[kind] = profile

        producer = {
            "actor": "agt006-producer",
            "agent_id": None,
            "machine": "vm1-developer",
            "provider": "openai",
            "model_family": "codex",
            "runtime": "codex-cli/pinned",
            "context_group": "agt006-producer-isolated-context",
            "package_digest": "f" * 64,
        }
        subject_digest = canonical_digest(
            {"pilot": "AGT-006", "kind": "successful-route"}
        )
        route_payload = {
            "subject_type": "agt006_pilot",
            "subject_id": "AGT006-INDEPENDENT-ROUTE",
            "subject_digest": subject_digest,
            "producer": producer,
            "required_review_kinds": ["statistical", "adversarial"],
            "required_capabilities": [],
            "max_pairwise_shared_dimensions": 4,
            "requested_by": "founder-operator",
        }
        route_digest = canonical_digest(route_payload)
        route = post_idempotent(
            client,
            "/v1/evaluator-routing/routes",
            route_payload,
            lambda: (
                client.get(
                    "/v1/evaluator-routing/routes",
                    params={"route_digest": route_digest},
                )
                .raise_for_status()
                .json()[0]
            ),
        )
        for assignment in route["assignments"]:
            if assignment["status"] == "completed":
                continue
            profile = profiles[assignment["review_kind"]]
            review_digest = canonical_digest(
                {
                    "assignment_digest": assignment["assignment_digest"],
                    "verdict": "reviewed",
                    "capital_authority": False,
                }
            )
            response = client.post(
                f"/v1/evaluator-routing/routes/{route['id']}/assignments/{assignment['id']}/complete",
                json={
                    "evaluator_agent_id": profile["agent_id"],
                    "review_id": f"AGT006-{assignment['review_kind'].upper()}-REVIEW",
                    "review_digest": review_digest,
                },
            )
            response.raise_for_status()
            route = response.json()
        assertion = (
            client.get(f"/v1/evaluator-routing/routes/{route['id']}/assertion")
            .raise_for_status()
            .json()
        )

        strict_payload = {
            **route_payload,
            "subject_id": "AGT006-CORRELATION-BLOCK",
            "subject_digest": canonical_digest(
                {"pilot": "AGT-006", "kind": "correlation-block"}
            ),
            "max_pairwise_shared_dimensions": 0,
        }
        strict_digest = canonical_digest(strict_payload)
        blocked = post_idempotent(
            client,
            "/v1/evaluator-routing/routes",
            strict_payload,
            lambda: (
                client.get(
                    "/v1/evaluator-routing/routes",
                    params={"route_digest": strict_digest},
                )
                .raise_for_status()
                .json()[0]
            ),
        )
    report = {
        "schema_version": "agt006-pilot-report-v1.0.0",
        "route_id": route["id"],
        "route_digest": route["route_digest"],
        "status": route["status"],
        "review_kinds": sorted(item["review_kind"] for item in route["assignments"]),
        "distinct_agents": len({profiles[item]["agent_id"] for item in profiles}),
        "distinct_packages": len(
            {profiles[item]["package_digest"] for item in profiles}
        ),
        "shared_runtime_dimensions": sorted(
            {
                dimension
                for item in route["assignments"]
                for dimension in item["correlation_report"]["producer"][
                    "shared_dimensions"
                ]
            }
        ),
        "independence_receipt_digest": assertion["receipt_digest"],
        "strict_correlation_route_status": blocked["status"],
        "strict_correlation_block_reason": blocked["blocked_reason"],
        "action_authority": False,
        "event_chain": [item["event_digest"] for item in route["events"]],
    }
    report["report_digest"] = canonical_digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
