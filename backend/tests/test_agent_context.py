from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.schemas.agent_context import (
    AgentContextCreate,
    ContextSource,
    WorkingMemoryCreate,
)
from app.services.agent_context import (
    create_context,
    digest,
    discard_working_memory,
    record_working_memory,
)
from fastapi import HTTPException
from pydantic import ValidationError


def request(task_id, agent_id, object_ids, **overrides):
    value = {
        "task_id": task_id,
        "agent_id": agent_id,
        "attempt_number": 1,
        "purpose": "Execute one bounded evidence-grounded task.",
        "sources": [
            ContextSource(
                object_id=item,
                selection_reason=f"required source {index}",
                prompt_position=index,
            )
            for index, item in enumerate(object_ids)
        ],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "created_by": "founder-operator",
    }
    value.update(overrides)
    return AgentContextCreate(**value)


def database(
    *,
    access_class="internal",
    state="active",
    payload_size=10,
    project="bulletproof_bt",
):
    task_id, agent_id, first, second = uuid4(), uuid4(), uuid4(), uuid4()
    task = SimpleNamespace(
        id=task_id,
        project="bulletproof_bt",
        attempt_count=0,
        assigned_agent_id=None,
        deadline_at=None,
        input_contract={},
    )
    agent = SimpleNamespace(id=agent_id)
    records = [
        SimpleNamespace(
            id=first,
            object_type="claim",
            content_digest="b" * 64,
            access_class=access_class,
            project=project,
            payload={"text": "x" * payload_size},
        ),
        SimpleNamespace(
            id=second,
            object_type="review",
            content_digest="c" * 64,
            access_class="internal",
            project=project,
            payload={"text": "opposition"},
        ),
    ]
    states = [
        SimpleNamespace(object_id=item.id, active_for_retrieval=(state == "active"))
        for item in records
    ]
    edge = SimpleNamespace(subject_id=first, object_id=second)
    db = MagicMock()
    db.get.side_effect = lambda model, key: (
        task if key == task_id else agent if key == agent_id else None
    )
    db.scalars.side_effect = [records, states, [edge]]
    return db, task_id, agent_id, first, second


def test_schema_rejects_ambiguous_positions_and_unsafe_scratch_paths():
    ids = [uuid4(), uuid4()]
    with pytest.raises(ValidationError, match="contiguous"):
        request(
            uuid4(),
            uuid4(),
            ids,
            sources=[
                ContextSource(
                    object_id=ids[0], selection_reason="first source", prompt_position=0
                ),
                ContextSource(
                    object_id=ids[1],
                    selection_reason="second source",
                    prompt_position=2,
                ),
            ],
        )
    with pytest.raises(ValidationError, match="task-relative"):
        WorkingMemoryCreate(
            lease_token="x" * 32,
            sequence=1,
            kind="scratch",
            content_digest="d" * 64,
            workspace_path="../escape.txt",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )


def test_context_is_bounded_replayable_and_surfaces_opposition():
    db, task_id, agent_id, first, second = database()
    with patch(
        "app.services.tasks.resolve_task_authority",
        return_value=[{"allowed": True, "snapshot_digest": "a" * 64}],
    ):
        record = create_context(db, request(task_id, agent_id, [first, second]))
    assert record.item_count == 2
    assert record.context_pack["items"][0]["citation"]["contradicts"] == [str(second)]
    assert record.context_pack_digest == digest(record.context_pack)
    assert len(record.manifest_digest) == 64 and record.status == "locked"


@pytest.mark.parametrize(
    ("access_class", "state", "status"),
    [("protected", "active", 403), ("internal", "retracted", 409)],
)
def test_protected_and_stale_context_fail_closed(access_class, state, status):
    db, task_id, agent_id, first, _ = database(access_class=access_class, state=state)
    with (
        patch(
            "app.services.tasks.resolve_task_authority",
            return_value=[{"allowed": True}],
        ),
        pytest.raises(HTTPException) as exc,
    ):
        create_context(db, request(task_id, agent_id, [first]))
    assert exc.value.status_code == status


def test_contamination_and_oversized_context_fail_closed():
    db, task_id, agent_id, first, _ = database(project="unrelated-project")
    with (
        patch(
            "app.services.tasks.resolve_task_authority",
            return_value=[{"allowed": True}],
        ),
        pytest.raises(HTTPException) as exc,
    ):
        create_context(db, request(task_id, agent_id, [first]))
    assert exc.value.status_code == 422
    db, task_id, agent_id, first, _ = database(payload_size=3000)
    with (
        patch(
            "app.services.tasks.resolve_task_authority",
            return_value=[{"allowed": True}],
        ),
        pytest.raises(HTTPException) as exc,
    ):
        create_context(db, request(task_id, agent_id, [first], max_bytes=1024))
    assert exc.value.status_code == 413


def test_working_memory_is_digest_only_and_discarded():
    context = SimpleNamespace(
        id=uuid4(),
        task_id=uuid4(),
        agent_id=uuid4(),
        manifest_digest="e" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    payload = WorkingMemoryCreate(
        lease_token="secret-lease-token" * 3,
        sequence=1,
        kind="observation",
        content_digest="f" * 64,
        workspace_path="scratch/observation.json",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db = MagicMock()
    receipt = record_working_memory(db, context, payload)
    assert receipt.content_digest == "f" * 64 and "secret-lease-token" not in str(
        receipt.__dict__
    )
    stored = SimpleNamespace(status="active", discarded_at=None)
    db.scalars.return_value = [stored]
    assert discard_working_memory(db, context.task_id) == 1
    assert stored.status == "discarded" and stored.discarded_at is not None
