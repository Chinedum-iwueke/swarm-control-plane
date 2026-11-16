"""Bounded offline reconstruction benchmark; never publishes production receipts."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from swarm_worker.executors.code_validation import AsyncProcessRunner
from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
from swarm_worker.policy import EngineeringMissionContract
from swarm_worker.provider_capacity import detect_provider_capacity
from swarm_worker.workspace import TaskWorkspace, WorkspaceMetadata, WorkspacePlan

TARGET = "src/bt/strategy/btc_5m_impact_proxy_reversal.py"
CARD = "research/hypotheses/alpha_003_btc_5m_impact_proxy_reversal.yaml"
TEST = "tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py"


def command(args, cwd, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source, commit, root, lane):
    folder = root / lane
    repo = folder / "repository"
    repo.mkdir(parents=True)
    archive = command(["git", "archive", commit], source).stdout
    command(["tar", "-xf", "-"], repo, input=archive)
    (repo / TARGET).unlink()
    # No original implementation or git history is available in either fixture.
    command(["git", "init", "-q"], repo)
    command(["git", "add", "."], repo)
    command(["git", "-c", "user.name=Parity", "-c", "user.email=parity@localhost",
             "commit", "-qm", "Frozen reconstruction fixture"], repo)
    logs, artifacts = folder / "logs", folder / "artifacts"
    logs.mkdir()
    artifacts.mkdir()
    task_id = uuid4()
    plan = WorkspacePlan(task_id, lane, 1, "bulletproof_bt", source, folder, repo,
                         logs, artifacts, folder / "metadata.json", commit, commit)
    metadata = WorkspaceMetadata(task_id=task_id, task_number=lane, attempt_number=1,
        repository="bulletproof_bt", source_repository=source, workspace_repository=repo,
        base_ref=commit, resolved_base_commit=commit, created_at=datetime.now(timezone.utc))
    return TaskWorkspace(plan, metadata)


async def main(args):
    os.umask(0o077)
    source = args.source.resolve()
    commit = command(["git", "rev-parse", args.commit + "^{commit}"], source).stdout.decode().strip()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, PYTHONPATH="src", OPENBLAS_NUM_THREADS="1",
                       OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    python = str(args.venv.resolve() / "bin/python")
    objective = (
        f"Implement the missing {TARGET} from the retained hypothesis card {CARD}. "
        "Use Btc5mImpactProxyReversalStrategy and the existing native strategy API. "
        "Read the card, frozen regression tests and neighboring strategies to understand semantics. "
        "Preserve prior-only cutoffs, completed-bar timing, missing-data behavior and native order semantics. "
        f"Run python -m pytest -q {TEST}. Only create the missing strategy module; "
        "do not edit tests, card, registry or other files. Do not inspect another checkout or git history, "
        "use the internet, access credentials, run live orders or invoke additional LLMs. "
        "This is offline reconstruction, not scientific certification."
    )
    contract = EngineeringMissionContract(repository="bulletproof_bt", workflow="engineering-mission",
        base_ref=commit, milestone_id="PARITY-NATIVE", work_item_id="impact-reversal",
        objective=objective, allowed_paths=[TARGET], context_paths=[CARD, TEST],
        acceptance_criteria=["Frozen native regression tests pass without modification.",
                             "Only the missing strategy module is added."],
        stop_conditions=["The frozen card and tests conflict or the dependency runtime is unavailable."],
        max_files_changed=1, max_diff_lines=2000, max_duration_seconds=args.timeout)
    executor = EngineeringMissionExecutor(codex_home=args.codex_home, codex_model=args.model,
        timeout_seconds=args.timeout, heartbeat_interval_seconds=15,
        process_runner=AsyncProcessRunner(environment=environment, virtualenv=args.venv),
        author_provider="codex")
    report = dict(schema_version="native-authoring-parity-v1", source_commit=commit,
        model=args.model, timeout_per_lane=args.timeout, reconstruction_only=True,
        full_autonomous_pipeline_tested=False, capital_or_order_authority=False, lanes={})
    for lane in ("direct", "worker"):
        workspace = prepare(source, commit, root, lane)
        frozen = {p.relative_to(workspace.repository).as_posix(): digest(p)
                  for p in workspace.repository.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(workspace.repository).parts}
        (workspace.artifacts / "frozen-manifest.json").write_text(json.dumps(frozen, sort_keys=True))
        baseline = subprocess.run([python, "-m", "pytest", "-q", TEST],
            cwd=workspace.repository, env=environment, capture_output=True, text=True, timeout=120)
        (workspace.logs / "missing-module.log").write_text(baseline.stdout + baseline.stderr)
        if baseline.returncode == 0 or "ModuleNotFoundError" not in baseline.stdout + baseline.stderr:
            raise RuntimeError("Missing-module negative control did not fail as expected")

        async def heartbeat(payload):
            (workspace.artifacts / "heartbeat.json").write_text(json.dumps(payload, default=str))

        prompt = objective if lane == "direct" else executor._coding_prompt(contract)
        failures = []
        step = await executor._run_author(contract=contract, prompt=prompt, workspace=workspace,
            heartbeat=heartbeat, heartbeat_failures=failures, timeout_seconds=args.timeout)
        mutated = [p for p, sha in frozen.items()
                   if not (workspace.repository / p).is_file() or digest(workspace.repository / p) != sha]
        status = command(["git", "status", "--porcelain", "--untracked-files=all"], workspace.repository).stdout.decode()
        scope_ok = not mutated and status.strip() == "?? " + TARGET
        test = subprocess.run([python, "-m", "pytest", "-q", TEST],
            cwd=workspace.repository, env=environment, capture_output=True, text=True, timeout=120)
        (workspace.logs / "frozen-tests.log").write_text(test.stdout + test.stderr)
        report["lanes"][lane] = dict(author=step.model_dump(mode="json"),
            heartbeat_failures=failures, frozen_files_changed=mutated, git_status=status,
            card_digest=frozen[CARD], test_digest=frozen[TEST],
            implementation_digest=digest(workspace.repository / TARGET) if (workspace.repository / TARGET).is_file() else None,
            scope_ok=scope_ok, test_returncode=test.returncode,
            accepted=step.success and scope_ok and test.returncode == 0)
        capacity = detect_provider_capacity([step], workspace.plan.attempt_directory,
                                            {step.name: "codex"})
        if capacity:
            report["capacity_blocker"] = capacity
        (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"lane": lane, "result": report["lanes"][lane]}), flush=True)
        if capacity:
            break
    return 0 if len(report["lanes"]) == 2 and all(x["accepted"] for x in report["lanes"].values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
