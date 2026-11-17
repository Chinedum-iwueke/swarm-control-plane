"""Durable, budgeted orchestration; model output never grants acceptance authority."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EngineeringEpisodePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=1)
    max_repairs: int = Field(default=2, ge=0, le=3)
    max_model_calls: int = Field(default=8, ge=2, le=12)
    max_adjudications: int = Field(default=1, ge=0, le=2)
    focused_tests: list[str] = Field(min_length=1, max_length=20)
    review_tests: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("focused_tests", "review_tests")
    @classmethod
    def safe_selectors(cls, values):
        for value in values:
            path = value.split("::", 1)[0]
            if (not re.fullmatch(r"tests/[A-Za-z0-9_/.-]+\.py(?:::[A-Za-z0-9_]+)*", value)
                    or ".." in Path(path).parts):
                raise ValueError("episode tests must be explicit repository test selectors")
        return values


def canonical_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class EpisodeIntegrityError(RuntimeError):
    pass


class EpisodeStore:
    def __init__(self, root: Path, binding: dict, duration: float, workspace: str):
        self.root, self.binding = root, binding
        self.duration, self.workspace = duration, workspace

    @contextmanager
    def locked(self):
        if self.root.is_symlink():
            raise EpisodeIntegrityError("episode root must not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.root / "lock"
        if lock.is_symlink():
            raise EpisodeIntegrityError("episode lock must not be a symlink")
        with lock.open("a+") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise EpisodeIntegrityError("episode already executing") from error
            yield

    def load(self):
        path = self.root / "state.json"
        if not path.exists():
            now = time.time()
            return dict(version=1, binding=self.binding, workspace=self.workspace,
                started_at=now, deadline=now + self.duration, stage="prepare", status="running",
                repairs=0, model_calls=0, adjudications=0, pending=None, code_digest=None,
                events=[], metrics={"model_seconds": 0.0, "deterministic_seconds": 0.0,
                    "reported_tokens": 0, "model_calls_without_usage": 0, "review_rejections": 0,
                    "review_recheck_acceptances": 0})
        if path.is_symlink() or path.stat().st_size > 4_000_000:
            raise EpisodeIntegrityError("invalid episode state file")
        envelope = json.loads(path.read_text())
        state = envelope["state"]
        if envelope["digest"] != canonical_digest(state) or state["binding"] != self.binding:
            raise EpisodeIntegrityError("episode binding or state digest mismatch")
        return state

    def save(self, state):
        fd, name = tempfile.mkstemp(dir=self.root, prefix="state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"state": state, "digest": canonical_digest(state)}, stream, sort_keys=True, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.root / "state.json")
            directory = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)


class EngineeringEpisode:
    """Callbacks execute approved tools; this controller owns transitions and budgets."""
    MODEL_STAGES = {"author", "review", "adjudicate"}
    READ_ONLY_STAGES = {"focused", "review_checks", "review", "adjudicate", "validation", "bundle"}

    def __init__(self, store: EpisodeStore, policy: EngineeringEpisodePolicy,
                 fingerprint: Callable[[], str], perform: Callable[..., Awaitable[dict]],
                 restore: Callable[[dict], None] | None = None,
                 before_stage: Callable[..., Awaitable[dict]] | None = None):
        self.store, self.policy = store, policy
        self.fingerprint, self.perform = fingerprint, perform
        self.restore = restore
        self.before_stage = before_stage

    async def run(self, *, recovery_token=None):
        with self.store.locked():
            state = self.store.load()
            if self.restore:
                self.restore(state)
            if state["status"] not in {"running", "deferred"}:
                if state["status"] == "completed" and self.fingerprint() != state["code_digest"]:
                    self._finish(state, "completed_workspace_changed")
                    self.store.save(state)
                return state
            if state['status'] == 'deferred':
                if not recovery_token or recovery_token == state.get('recovery_token'):
                    return state
            state['recovery_token'] = recovery_token
            state["status"] = "running"
            state.pop('reason', None)
            if state["pending"] is not None:
                state["events"].append({"stage": state["stage"], "status": "interrupted",
                                        "reservation": state["pending"]})
                state["pending"] = None
            while state["status"] == "running":
                stage = state["stage"]
                if stage == "adjudicate" and state["adjudications"] >= self.policy.max_adjudications:
                    self._finish(state, "review_disputed")
                    break
                remaining = state["deadline"] - time.time()
                if remaining <= 0:
                    self._finish(state, "deadline_exhausted")
                    break
                if self.before_stage:
                    permit = await self.before_stage(stage, state)
                    if permit.get('allowed') is not True:
                        state.update(status='deferred', reason=permit.get('reason', 'authority'))
                        break
                    remaining = state['deadline'] - time.time()
                    if remaining <= 0:
                        self._finish(state, 'deadline_exhausted')
                        break
                before = self.fingerprint()
                if state["code_digest"] and before != state["code_digest"] and stage not in {"prepare", "author"}:
                    state["stage"] = stage = "focused"
                    state["events"].append({"status": "acceptance_invalidated", "code_digest": before})
                if stage in self.MODEL_STAGES:
                    if state["model_calls"] >= self.policy.max_model_calls:
                        self._finish(state, "model_budget_exhausted")
                        break
                    state["model_calls"] += 1
                # Reserve before the external side effect, including calls interrupted by a crash.
                reservation = len(state["events"])
                state["pending"] = reservation
                self.store.save(state)
                started = time.monotonic()
                result = await self.perform(stage, state, remaining, reservation)
                elapsed = time.monotonic() - started
                after = self.fingerprint()
                if stage in self.READ_ONLY_STAGES and after != before:
                    result = {"status": "policy_violation", "reason": "read_only_stage_changed_code"}
                event = {"stage": stage, "code_digest": after, "duration_seconds": elapsed,
                         "result": result, "receipt_id": canonical_digest([self.store.binding, reservation, stage, after, result])}
                state["events"].append(event)
                state["pending"] = None
                state["code_digest"] = after
                state["metrics"]["model_seconds" if stage in self.MODEL_STAGES else "deterministic_seconds"] += elapsed
                if stage in self.MODEL_STAGES:
                    if isinstance(result.get("reported_tokens"), int):
                        state["metrics"]["reported_tokens"] += result["reported_tokens"]
                    else:
                        state["metrics"]["model_calls_without_usage"] += 1
                status = result["status"]
                if status in {"capacity", "infrastructure"}:
                    state["status"] = "deferred"
                    state["reason"] = status
                elif status == "policy_violation":
                    self._finish(state, "policy_violation")
                elif status == "pass":
                    if stage == "review" and state.get("recheck_digest") == after:
                        state["metrics"]["review_recheck_acceptances"] += 1
                    if stage in {"review", "author"}:
                        state.pop("recheck_digest", None)
                    state["stage"] = {"prepare": "author", "author": "focused", "focused": "review",
                        "review_checks": "adjudicate", "review": "validation", "validation": "bundle",
                        "bundle": "done"}.get(stage, "disputed")
                    if state["stage"] == "done":
                        state["status"] = "completed"
                    elif state["stage"] == "disputed":
                        self._finish(state, "review_disputed")
                elif stage == "review" and status == "rejected":
                    state["metrics"]["review_rejections"] += 1
                    state["stage"] = "review_checks"
                elif stage == "adjudicate" and status == "recheck":
                    evidence = result.get("evidence_receipts", [])
                    valid = {e["receipt_id"] for e in state["events"] if e.get("stage") in {"focused", "review_checks"}
                             and e.get("code_digest") == after and e.get("result", {}).get("status") == "pass"}
                    if (not isinstance(evidence, list) or not evidence
                            or not all(isinstance(item, str) for item in evidence)
                            or not set(evidence) <= valid
                            or state["adjudications"] >= self.policy.max_adjudications):
                        self._finish(state, "review_disputed")
                    else:
                        state["adjudications"] += 1
                        state["recheck_digest"] = after
                        state["stage"] = "review"
                elif stage in {"focused", "review_checks", "validation"} and status == "fail":
                    if state["repairs"] >= self.policy.max_repairs:
                        self._finish(state, "repair_budget_exhausted")
                    else:
                        state["repairs"] += 1
                        state["stage"] = "author"
                else:
                    self._finish(state, "review_disputed" if stage == "adjudicate" else f"{stage}_blocked")
                self.store.save(state)
            self.store.save(state)
            return state

    @staticmethod
    def _finish(state, reason):
        state["status"], state["reason"] = "blocked", reason
