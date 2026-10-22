from __future__ import annotations

from datetime import datetime, timezone

from hermes_mission_control.agent_detail import project_agent_detail

NOW = datetime(2026, 10, 22, 13, tzinfo=timezone.utc)
AGENT_ID = "agent-1"


def snapshot() -> dict:
    return {
        "agents": [
            {
                "id": AGENT_ID,
                "slug": "alpha-reviewer",
                "display_name": "Alpha Reviewer",
                "role": "reviewer",
                "machine": "vm1-developer",
                "hermes_profile": "restricted",
                "runtime": "native",
                "runtime_version": "1.0.0",
                "status": "online",
                "presence": "online",
                "capabilities": ["review"],
                "risk_ceiling": 1,
                "is_enabled": True,
                "last_heartbeat_at": "2026-10-22T12:59:30+00:00",
                "credential": "must-not-leak",
            }
        ],
        "package_deployments": [
            {
                "deployment": {
                    "id": "deployment-1",
                    "agent_id": AGENT_ID,
                    "is_active": True,
                },
                "package": {
                    "id": "package-1",
                    "name": "alpha-reviewer",
                    "version": "2.0.0",
                    "manifest_digest": "a" * 64,
                    "source_commit": "b" * 40,
                },
            }
        ],
        "agent_charters": [
            {
                "id": "charter-1",
                "agent_id": AGENT_ID,
                "status": "active",
                "version": "1.0.0",
                "manifest_digest": "c" * 64,
                "manifest": {
                    "role": "reviewer",
                    "responsibilities": ["independent review"],
                    "capabilities": ["review"],
                    "allowed_task_types": ["research_experiment"],
                    "risk_ceiling": 1,
                },
            }
        ],
        "agent_capability_grants": [
            {
                "id": "grant-1",
                "agent_id": AGENT_ID,
                "status": "active",
                "capability": "review",
                "machine": "vm1-developer",
                "task_types": ["research_experiment"],
                "repositories": ["bulletproof_bt"],
                "risk_ceiling": 1,
                "accountable_owner": "founder",
                "expires_at": "2026-10-23T00:00:00+00:00",
                "record_digest": "d" * 64,
            }
        ],
        "workload_identities": {
            "identities": [
                {
                    "id": "identity-1",
                    "agent_id": AGENT_ID,
                    "status": "active",
                    "version": "1",
                    "machine": "vm1-developer",
                    "audience": "control-plane",
                    "scopes": ["task:lease"],
                    "accountable_owner": "founder",
                    "manifest_digest": "e" * 64,
                }
            ]
        },
        "operations": [
            {
                "id": "operation-1",
                "operation_key": "task:task-1",
                "owner_id": AGENT_ID,
                "owner_type": "agent",
                "state": "running",
                "phase": "review",
                "title": "Review a bounded strategy",
                "machine": "vm1-developer",
                "heartbeat_at": "2026-10-22T12:59:30+00:00",
                "detail": {},
                "links": {"log": "artifact://review.log"},
            }
        ],
        "artifacts": [
            {
                "id": "artifact-1",
                "task_id": "task-1",
                "name": "review.json",
                "artifact_type": "evidence",
                "sha256": "f" * 64,
                "verification_status": "verified",
                "location": "workspace",
            }
        ],
    }


def tasks() -> list[dict]:
    return [
        {
            "id": "task-1",
            "task_number": "A3-1",
            "title": "Review a bounded strategy",
            "project": "bulletproof_bt",
            "task_type": "research_experiment",
            "status": "running",
            "risk_level": 1,
            "attempt_count": 1,
            "max_attempts": 2,
            "updated_at": "2026-10-22T12:59:30+00:00",
        }
    ]


def test_agent_detail_binds_identity_governance_lease_history_and_references():
    detail = project_agent_detail(
        snapshot(), AGENT_ID, tasks(), offset=0, limit=25, now=NOW
    )
    assert detail is not None
    assert detail["agent"]["slug"] == "alpha-reviewer"
    assert "credential" not in detail["agent"]
    assert detail["deployment"]["package_name"] == "alpha-reviewer"
    assert detail["charter"]["role"] == "reviewer"
    assert detail["current_lease"]["id"] == "operation-1"
    assert detail["task_history"]["items"][0]["task_number"] == "A3-1"
    assert detail["references"]["artifacts"][0]["name"] == "review.json"
    assert detail["references"]["logs"][0]["reference"] == "artifact://review.log"
    assert detail["provenance"]["presence"] == {
        "source_key": "agents",
        "source_identity": "control-plane:/v1/agents",
        "fact_class": "canonical",
        "freshness": "current",
        "freshness_threshold_seconds": 120,
        "source_timestamp": "2026-10-22T12:59:30+00:00",
        "reason": None,
    }
    assert detail["provenance"]["task_status"]["source_identity"] == (
        "control-plane:/v1/tasks"
    )
    assert detail["provenance"]["task_status"]["freshness"] == "current"


def test_agent_detail_marks_reporting_and_heartbeat_history_unknown_without_authority():
    detail = project_agent_detail(snapshot(), AGENT_ID, [], offset=0, limit=25, now=NOW)
    assert detail is not None
    assert detail["reporting_relationship"] == {
        "status": "unknown",
        "reason": "no_authoritative_relationship_record",
    }
    assert detail["heartbeat_history"]["availability"] == "current_observation_only"
    assert detail["task_history"]["has_more"] is False
    assert detail["provenance"]["task_status"]["freshness"] == "unknown"
    assert detail["provenance"]["task_status"]["reason"] == ("source_timestamp_missing")


def test_agent_detail_preserves_stale_agent_and_multiple_attempt_history_without_assignment():
    value = snapshot()
    value["agents"][0]["presence"] = "offline"
    value["agents"][0]["status"] = "degraded"
    value["agents"][0]["last_heartbeat_at"] = "2026-10-22T12:40:00+00:00"
    value["agents"][0]["updated_at"] = "2026-10-22T12:59:59+00:00"
    value["package_deployments"] = [
        {
            "deployment": {
                "id": "expired-deployment",
                "agent_id": AGENT_ID,
                "is_active": False,
            },
            "package": {"name": "expired-package"},
        }
    ]
    value["operations"] = []
    history = [
        {**tasks()[0], "status": "failed", "attempt_count": 1},
        {
            **tasks()[0],
            "id": "task-2",
            "task_number": "A3-2",
            "status": "succeeded",
            "attempt_count": 2,
        },
    ]
    detail = project_agent_detail(value, AGENT_ID, history, offset=0, limit=2, now=NOW)
    assert detail is not None
    assert detail["agent"]["presence"] == "offline"
    assert detail["deployment"] is None
    assert detail["current_lease"] is None
    assert [item["attempt_count"] for item in detail["task_history"]["items"]] == [1, 2]
    assert detail["task_history"]["has_more"] is True
    assert detail["provenance"]["presence"]["freshness"] == "stale"
    assert detail["provenance"]["presence"]["source_timestamp"] == (
        "2026-10-22T12:40:00+00:00"
    )


def test_agent_detail_returns_none_for_an_unknown_agent():
    assert (
        project_agent_detail(snapshot(), "not-agent", [], offset=0, limit=25, now=NOW)
        is None
    )
