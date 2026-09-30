import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "agt001_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("agt001_bootstrap", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
next_identity_version = MODULE.next_identity_version
workload_scopes = MODULE.workload_scopes
charter_covers_package = MODULE.charter_covers_package


def test_workload_scopes_follow_role_package_task_types() -> None:
    assert workload_scopes(
        {
            "task_types": [
                "engineering_mission",
                "research_synthesis",
                "fleet_observation",
            ]
        }
    ) == [
        "control:read",
        "fleet:write",
        "heartbeat:write",
        "identity:read",
        "package:read",
        "research:write",
        "task:execute",
        "task:lease",
    ]


def test_next_identity_version_is_monotonic() -> None:
    identities = [
        {"agent_id": "agent-a", "version": "1.0.0"},
        {"agent_id": "agent-a", "version": "1.0.2"},
        {"agent_id": "agent-b", "version": "1.0.1"},
    ]

    assert next_identity_version(identities, "agent-a") == "1.0.3"


def test_existing_stricter_charter_covers_active_package() -> None:
    charter = {
        "agent_id": "agent-a",
        "status": "active",
        "manifest": {
            "allowed_machines": ["vm1-developer"],
            "capabilities": ["git", "python", "testing"],
            "allowed_task_types": ["engineering_mission"],
            "allowed_repositories": ["bulletproof_bt"],
            "risk_ceiling": 1,
        },
    }
    package_manifest = {
        "required_capabilities": ["git", "python"],
        "task_types": ["engineering_mission"],
        "repository_profile": {"repositories": ["bulletproof_bt"]},
        "risk_ceiling": 0,
    }

    assert charter_covers_package(
        charter,
        {"id": "agent-a", "machine": "vm1-developer"},
        package_manifest,
    )
