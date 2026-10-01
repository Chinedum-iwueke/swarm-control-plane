from app.api.routes.tasks import _compact_task_payload


def test_compact_task_projection_omits_unbounded_scientific_payloads() -> None:
    payload = {
        "input_contract": {
            "workflow": "engineering-mission",
            "milestone_id": "ALPHA-003",
            "scientific_context": "x" * 1_000_000,
        },
        "expected_outputs": ["large output contract"],
        "acceptance_criteria": ["large acceptance contract"],
        "approval_policy": {"large": "policy"},
        "result": {
            "success": True,
            "workflow": "engineering-mission",
            "base_commit": "a" * 40,
            "logs": "x" * 1_000_000,
        },
        "failure": {
            "category": "none",
            "message": "bounded message",
            "traceback": "x" * 1_000_000,
        },
    }

    compact = _compact_task_payload(payload)

    assert compact["input_contract"] == {
        "workflow": "engineering-mission",
        "milestone_id": "ALPHA-003",
    }
    assert compact["expected_outputs"] == []
    assert compact["acceptance_criteria"] == []
    assert compact["approval_policy"] == {}
    assert compact["result"] == {
        "success": True,
        "workflow": "engineering-mission",
        "base_commit": "a" * 40,
    }
    assert compact["failure"] == {
        "category": "none",
        "message": "bounded message",
    }
