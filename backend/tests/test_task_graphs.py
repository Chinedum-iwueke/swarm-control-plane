from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.task_graph import TaskGraphCreate
from app.services.task_graphs import _cancel_task, digest
from pydantic import ValidationError


def node(key: str, depends_on: list[str] | None = None, *, compensation=False) -> dict:
    spec = {
        "task_type": "bounded_analysis",
        "title": f"Run {key}",
        "objective": f"Produce the {key} result.",
        "expected_outputs": ["result.json"],
        "acceptance_criteria": ["Result validates against its declared type."],
        "max_attempts": 1,
    }
    return {
        "key": key,
        "role": "research-specialist",
        "depends_on": depends_on or [],
        "input_type": "research.input.v1",
        "output_type": "research.output.v1",
        "task": spec,
        "stop_conditions": ["Lease is lost or graph cancellation is requested."],
        "compensation": spec if compensation else None,
    }


def graph(nodes: list[dict], **overrides) -> dict:
    value = {
        "graph_key": "AGT003-PILOT",
        "project": "swarm-control-plane",
        "objective": "Exercise one bounded typed task graph.",
        "created_by": "founder-operator",
        "max_nodes": 8,
        "max_total_attempts": 8,
        "max_duration_seconds": 300,
        "max_parallelism": 2,
        "nodes": nodes,
    }
    value.update(overrides)
    return value


def test_graph_accepts_typed_bounded_dag() -> None:
    payload = TaskGraphCreate.model_validate(
        graph([node("spec"), node("execute", ["spec"], compensation=True)])
    )
    assert payload.nodes[1].output_type == "research.output.v1"
    assert payload.nodes[1].compensation is not None


@pytest.mark.parametrize(
    "nodes",
    [
        [node("a", ["b"]), node("b", ["a"])],
        [node("a", ["missing"])],
        [node("a"), node("a")],
    ],
)
def test_graph_rejects_cycles_missing_edges_and_duplicate_nodes(nodes: list[dict]) -> None:
    with pytest.raises(ValidationError):
        TaskGraphCreate.model_validate(graph(nodes))


def test_graph_rejects_runaway_attempt_budget() -> None:
    with pytest.raises(ValidationError, match="attempts exceed"):
        TaskGraphCreate.model_validate(graph([node("a"), node("b")], max_total_attempts=1))


def test_active_task_cancellation_is_cooperative_and_durable() -> None:
    db = MagicMock()
    task = SimpleNamespace(
        id="task-1", status="running", cancel_requested_at=None,
        cancel_reason=None, completed_at=None, attempt_count=1,
    )
    assert _cancel_task(db, task, "founder stopped graph") is True
    assert task.status == "running"
    assert task.cancel_requested_at <= datetime.now(UTC)
    assert task.cancel_reason == "founder stopped graph"
    db.add.assert_called_once()


def test_canonical_digest_is_order_independent() -> None:
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
