import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from swarm_worker.engineering_episode import (
    EngineeringEpisode, EngineeringEpisodePolicy, EpisodeIntegrityError, EpisodeStore,
)


def policy(**kwargs):
    return EngineeringEpisodePolicy(focused_tests=["tests/test_signal.py"], **kwargs)


def store(tmp_path, **kwargs):
    return EpisodeStore(tmp_path / "episode", {"contract": "frozen", "source": "pinned"},
                        kwargs.get("duration", 300), "workspace")


@pytest.mark.parametrize("selector", ["../test.py", "tests/../secrets.py", "tests/test.py;curl", "-k", "/tmp/test.py"])
def test_unapproved_commands_cannot_enter_test_policy(selector):
    with pytest.raises(ValidationError):
        EngineeringEpisodePolicy(focused_tests=[selector])


@pytest.mark.asyncio
@pytest.mark.parametrize("hypothesis", ["threshold_ties", "completed_bar_atr", "cross_asset_lag"])
async def test_bounded_repair_preserves_work_item_and_rechecks(tmp_path, hypothesis):
    calls, code = [], ["original"]

    async def perform(stage, state, remaining, sequence):
        calls.append(stage)
        if stage == "author":
            code[0] = f"{hypothesis}-revision-{state['repairs']}"
        if stage == "focused" and state["repairs"] == 0:
            return {"status": "fail", "evidence": hypothesis}
        return {"status": "pass"}

    result = await EngineeringEpisode(store(tmp_path), policy(), lambda: code[0], perform).run()
    assert result["status"] == "completed"
    assert result["repairs"] == 1
    assert calls == ["prepare", "author", "focused", "author", "focused", "review", "validation", "bundle"]
    assert result["model_calls"] == 3
    assert all(event.get("receipt_id") for event in result["events"])


@pytest.mark.asyncio
async def test_adjudication_never_approves_without_fresh_review(tmp_path):
    calls = []

    async def perform(stage, state, *_):
        calls.append(stage)
        if stage == "review":
            return {"status": "rejected" if state["adjudications"] == 0 else "pass"}
        if stage == "adjudicate":
            receipt = next(e["receipt_id"] for e in state["events"] if e.get("stage") == "review_checks")
            return {"status": "recheck", "evidence_receipts": [receipt], "reason": "loader rejects this input"}
        return {"status": "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(), lambda: "code", perform).run()
    assert state["status"] == "completed"
    assert calls == ["prepare", "author", "focused", "review", "review_checks", "adjudicate", "review", "validation", "bundle"]
    assert state["repairs"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["pass", "recheck", "disputed"])
@pytest.mark.parametrize("receipts", [["invented"], [{"invalid": "object"}], None, "receipt"])
async def test_unsupported_or_invented_adjudication_never_materializes(tmp_path, decision, receipts):
    async def perform(stage, *_):
        if stage == "review":
            return {"status": "rejected"}
        if stage == "adjudicate":
            return {"status": decision, "evidence_receipts": receipts}
        assert stage not in {"validation", "bundle"}
        return {"status": "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(), lambda: "code", perform).run()
    assert state["status"] == "blocked"
    assert state["reason"] == "review_disputed"


@pytest.mark.asyncio
async def test_review_counterexample_reenters_same_author_without_new_approval(tmp_path):
    async def perform(stage, state, *_):
        if stage == "review" and state["repairs"] == 0:
            return {"status": "rejected"}
        if stage == "review_checks":
            return {"status": "fail", "evidence": "threshold tie counterexample"}
        return {"status": "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(review_tests=["tests/test_ties.py"]), lambda: "code", perform).run()
    assert state["status"] == "completed"
    assert state["repairs"] == 1
    assert state["adjudications"] == 0


@pytest.mark.asyncio
async def test_crash_charges_call_and_retains_workspace_on_resume(tmp_path):
    calls = []

    async def crash(stage, *_):
        calls.append(stage)
        if stage == "author":
            raise RuntimeError("process interrupted")
        return {"status": "pass"}

    with pytest.raises(RuntimeError):
        await EngineeringEpisode(store(tmp_path), policy(), lambda: "partial code", crash).run()
    assert store(tmp_path).load()["model_calls"] == 1

    async def resume(stage, *_):
        calls.append(stage)
        return {"status": "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(), lambda: "partial code", resume).run()
    assert state["status"] == "completed"
    assert state["model_calls"] == 3
    assert calls.count("prepare") == 1
    assert any(e.get("status") == "interrupted" for e in state["events"])


@pytest.mark.asyncio
async def test_capacity_defers_without_consuming_repairs_or_retry_loop(tmp_path):
    async def perform(stage, *_):
        return {"status": "capacity" if stage == "author" else "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(), lambda: "code", perform).run()
    assert state["status"] == "deferred"
    assert state["repairs"] == 0
    assert state["model_calls"] == 1


@pytest.mark.asyncio
async def test_repair_budget_and_deadline_do_not_reset(tmp_path):
    calls = []

    async def perform(stage, *_):
        calls.append(stage)
        return {"status": "fail" if stage == "focused" else "pass"}

    engine = EngineeringEpisode(store(tmp_path), policy(max_repairs=1), lambda: "code", perform)
    first = await engine.run()
    count = len(calls)
    again = await engine.run()
    assert first["reason"] == again["reason"] == "repair_budget_exhausted"
    assert len(calls) == count
    expired = EngineeringEpisode(store(tmp_path / "expired", duration=-1), policy(), lambda: "code", perform)
    assert (await expired.run())["reason"] == "deadline_exhausted"
    assert len(calls) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("mutating_stage", ["review", "focused", "validation", "bundle"])
async def test_read_only_reviewer_cannot_mutate_code(tmp_path, mutating_stage):
    code = ["original"]

    async def perform(stage, *_):
        if stage == mutating_stage:
            code[0] = "tampered"
        return {"status": "pass"}

    state = await EngineeringEpisode(store(tmp_path), policy(), lambda: code[0], perform).run()
    assert state["reason"] == "policy_violation"


def test_binding_and_corruption_rejected(tmp_path):
    database = store(tmp_path)
    with database.locked():
        database.save(database.load())
        with pytest.raises(EpisodeIntegrityError, match="already executing"):
            with database.locked():
                pass
    wrong = EpisodeStore(database.root, {"contract": "changed"}, 300, "workspace")
    with pytest.raises(EpisodeIntegrityError):
        wrong.load()
    path = database.root / "state.json"
    value = json.loads(path.read_text())
    value["state"]["model_calls"] = -1
    path.write_text(json.dumps(value))
    with pytest.raises(EpisodeIntegrityError):
        database.load()


@pytest.mark.asyncio
async def test_completed_receipt_does_not_authorize_changed_code(tmp_path):
    code = ["reviewed"]

    async def perform(*_):
        return {"status": "pass"}

    engine = EngineeringEpisode(store(tmp_path), policy(), lambda: code[0], perform)
    assert (await engine.run())["status"] == "completed"
    code[0] = "changed"
    assert (await engine.run())["reason"] == "completed_workspace_changed"
