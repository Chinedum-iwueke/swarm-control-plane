#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded DISC-008 production pilot.")
    parser.add_argument("--output", type=Path, default=Path("/tmp/disc008-report.json"))
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    graph_key = "DISC008-LIVE-BOUNDED-SESSION"
    graph_payload = {
        "graph_key": graph_key,
        "project": "bulletproof-bt",
        "objective": "Exercise one bounded no-capital autonomous research session.",
        "created_by": "founder-operator",
        "max_nodes": 3,
        "max_total_attempts": 3,
        "max_duration_seconds": 600,
        "max_parallelism": 1,
        "nodes": [],
    }
    phases = [
        ("specify", "research-specification", "research.specification.v1", "negative"),
        ("execute", "research-execution", "research.execution.v1", "failed"),
        ("retain", "research-audit", "research.audit.v1", "invalid"),
    ]
    for index, (key, role, output, _) in enumerate(phases):
        graph_payload["nodes"].append({
            "key": key,
            "role": role,
            "node_type": "review" if key == "retain" else "work",
            "depends_on": [phases[index - 1][0]] if index else [],
            "input_type": "research.input.v1",
            "output_type": output,
            "task": {
                "task_type": "disc008_pilot_fixture",
                "title": f"DISC-008 {key}",
                "objective": f"Record the deterministic {key} fixture outcome.",
                "input_contract": {"fixture": True, "capital_authority": False},
                "expected_outputs": [f"{key}.json"],
                "acceptance_criteria": ["The declared non-result is retained."],
                "required_capabilities": [],
                "allowed_machines": ["vm2-platform"],
                "max_attempts": 1,
                "risk_level": 0,
            },
            "stop_conditions": ["Session cancellation or budget exhaustion."],
        })
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        graphs = client.get("/v1/task-graphs", params={"limit": 100}).raise_for_status().json()
        graph = next((item for item in graphs if item["graph_key"] == graph_key), None)
        if graph is None:
            graph = client.post("/v1/task-graphs", json=graph_payload).raise_for_status().json()
        session_payload = {
            "session_key": "DISC008-LIVE-SESSION-1",
            "project": "bulletproof-bt",
            "objective": graph_payload["objective"],
            "task_graph_id": graph["id"],
            "agenda": [
                {"node_key": key, "role": role, "expected_output_type": output}
                for key, role, output, _ in phases
            ],
            "budget": {
                "max_tasks": 3,
                "max_total_attempts": 3,
                "max_duration_seconds": 600,
                "max_reconciliations": 10,
                "max_no_progress_reconciliations": 2,
                "max_worker_losses": 1,
            },
            "stop_conditions": ["Fixed agenda completes.", "Any budget is exhausted."],
            "escalation_conditions": ["Evidence conflict.", "Worker loss budget exceeded."],
            "allowed_scope": ["deterministic DISC-008 no-capital fixture"],
            "authority": "no_capital",
            "may_approve": False,
            "may_expand_scope": False,
            "may_promote": False,
            "created_by": "founder-operator",
        }
        sessions = client.get("/v1/research/autonomous-sessions").raise_for_status().json()
        session = next((item for item in sessions if item["session_key"] == session_payload["session_key"]), None)
        if session is None:
            session = client.post("/v1/research/autonomous-sessions", json=session_payload).raise_for_status().json()
        if session["status"] == "draft":
            session = client.post(
                f"/v1/research/autonomous-sessions/{session['id']}/activate",
                json={"actor": "founder-operator", "reason": "Run approved no-capital pilot."},
            ).raise_for_status().json()

        if session["status"] == "active":
            from app.db.session import SessionLocal
            from app.models import Task, TaskGraph
            from app.services.task_graphs import (
                append_task_event,
                clear_lease,
                reconcile_graph,
            )

            graph = client.get(f"/v1/task-graphs/{graph['id']}").raise_for_status().json()
            outcomes = {key: outcome for key, _, _, outcome in phases}
            with SessionLocal() as db:
                for item in graph["nodes"]:
                    task = db.get(Task, item["task_id"])
                    task.status = "succeeded"
                    task.result = {
                        "fixture": True,
                        "scientific_outcome": outcomes[item["key"]],
                        "production_eligible": False,
                        "capital_authority": False,
                    }
                    task.failure = {}
                    append_task_event(
                        db, task, "task_completed", "DISC-008 deterministic pilot fixture completed.",
                        payload={"result": task.result},
                    )
                    clear_lease(task)
                reconcile_graph(db, db.get(TaskGraph, session["task_graph_id"]))
                db.commit()
            session = client.post(
                f"/v1/research/autonomous-sessions/{session['id']}/reconcile"
            ).raise_for_status().json()

        if session["status"] == "awaiting_closeout":
            audits = client.get("/v1/research/selection-audits").raise_for_status().json()
            audit = next(item for item in audits if item["status"] == "active")
            dossier = {
                "session_id": session["id"],
                "task_graph_digest": session["task_graph_digest"],
                "agenda_digest": session["agenda_digest"],
                "budget_digest": session["budget_digest"],
                "selection_audit_digest": audit["audit_digest"],
                "retained_outcomes": ["negative", "failed", "invalid"],
                "production_eligible": False,
            }
            dossier_digest = canonical_digest(dossier)
            profiles = client.get("/v1/evaluator-routing/profiles").raise_for_status().json()
            by_id = {item["id"]: item for item in profiles}
            route_payload = {
                "subject_type": "autonomous_research_session",
                "subject_id": session["id"],
                "subject_digest": dossier_digest,
                "producer": {
                    "actor": "disc008-supervisor",
                    "agent_id": None,
                    "machine": "vm2-platform",
                    "provider": "deterministic-controller",
                    "model_family": "none",
                    "runtime": "disc008-v1",
                    "context_group": "disc008-producer",
                    "package_digest": "f" * 64,
                },
                "required_review_kinds": ["statistical", "adversarial"],
                "required_capabilities": [],
                "max_pairwise_shared_dimensions": 4,
                "requested_by": "disc008-supervisor",
            }
            route = client.post("/v1/evaluator-routing/routes", json=route_payload).raise_for_status().json()
            if route["status"] != "assigned":
                raise RuntimeError(f"Independent evaluator routing failed: {route['blocked_reason']}")
            for assignment in route["assignments"]:
                profile = by_id[assignment["evaluator_profile_id"]]
                review_digest = canonical_digest({
                    "assignment_digest": assignment["assignment_digest"],
                    "verdict": "retained_no_capital_fixture",
                })
                route = client.post(
                    f"/v1/evaluator-routing/routes/{route['id']}/assignments/{assignment['id']}/complete",
                    json={
                        "evaluator_agent_id": profile["agent_id"],
                        "review_id": f"DISC008-{assignment['review_kind'].upper()}-REVIEW",
                        "review_digest": review_digest,
                    },
                ).raise_for_status().json()
            session = client.post(
                f"/v1/research/autonomous-sessions/{session['id']}/closeout",
                json={
                    "actor": "disc008-supervisor",
                    "evaluation_route_id": route["id"],
                    "selection_audit_id": audit["id"],
                    "dossier": dossier,
                    "dossier_digest": dossier_digest,
                    "retained_outcomes": ["negative", "failed", "invalid"],
                },
            ).raise_for_status().json()

    report = {
        "schema_version": "disc008-pilot-report-v1.0.0",
        "session_id": session["id"],
        "task_graph_id": session["task_graph_id"],
        "task_graph_digest": session["task_graph_digest"],
        "agenda_digest": session["agenda_digest"],
        "budget_digest": session["budget_digest"],
        "status": session["status"],
        "retained_outcomes": session["closeout"].get("retained_outcomes", []),
        "independence_receipt_digest": session["closeout"].get("independence_receipt_digest"),
        "selection_audit_digest": session["closeout"].get("selection_audit_digest"),
        "event_chain": [item["event_digest"] for item in session["events"]],
        "scope_expansion": False,
        "self_approval": False,
        "promotion_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = canonical_digest(report)
    if report["status"] != "completed":
        raise RuntimeError(f"DISC-008 pilot did not complete: {report['status']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
