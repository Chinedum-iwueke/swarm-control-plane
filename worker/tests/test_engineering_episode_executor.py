import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from swarm_worker.engineering_episode import EngineeringEpisodePolicy
from swarm_worker.executors.code_validation import AsyncProcessRunner, CodeValidationExecutor
from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
from swarm_worker.models import StepExecutionResult
from swarm_worker.policy import EngineeringMissionContract
from swarm_worker.workflows import WorkflowDefinition
from swarm_worker.workspace import TaskWorkspace, WorkspaceMetadata, WorkspacePlan


def step(name, workspace):
    for stream in ("stdout", "stderr"):
        (workspace.logs / f"{name}.{stream}.log").write_text("")
    now = datetime.now(timezone.utc)
    return StepExecutionResult(name=name, success=True, return_code=0, started_at=now,
        ended_at=now, duration_seconds=0, stdout_log=f"logs/{name}.stdout.log", stderr_log=f"logs/{name}.stderr.log")


def fixture(tmp_path, expression, expected):
    attempt = tmp_path / "task" / "attempt-1"
    repo = attempt / "repository"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests/test_signal.py").write_text(f"from signal_logic import signal\ndef test_signal():\n    assert signal() == {expected!r}\n")
    (repo / "signal_logic.py").write_text("def signal():\n    return None\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    for command in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.name=Test",
                    "-c", "user.email=test@localhost", "commit", "-qm", "baseline"]):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    task_id = uuid4()
    logs, artifacts = attempt / "logs", attempt / "artifacts"
    logs.mkdir()
    artifacts.mkdir()
    plan = WorkspacePlan(task_id, "EPISODE", 1, "fixture", repo, attempt, repo,
                         logs, artifacts, attempt / "metadata.json", commit, commit)
    metadata = WorkspaceMetadata(task_id=task_id, task_number="EPISODE", attempt_number=1,
        repository="fixture", source_repository=repo, workspace_repository=repo,
        base_ref=commit, resolved_base_commit=commit, created_at=datetime.now(timezone.utc))
    workspace = TaskWorkspace(plan, metadata)
    contract = EngineeringMissionContract(repository="fixture", workflow="engineering-mission", base_ref=commit,
        milestone_id="EPISODE-TEST", work_item_id="signal", objective="Implement the immutable signal specification.",
        allowed_paths=["signal_logic.py"], acceptance_criteria=["Frozen regression passes"],
        stop_conditions=["Scope cannot expand"], max_files_changed=1, max_diff_lines=40, max_duration_seconds=60,
        engineering_episode=EngineeringEpisodePolicy(focused_tests=["tests/test_signal.py"]))
    task = SimpleNamespace(id=task_id, task_number="EPISODE", task_type="engineering_mission", attempt_count=1,
                           prior_failure=None, input_contract=contract.model_dump(mode="json"))
    workflow = WorkflowDefinition(name="engineering-mission", task_type="engineering_mission", timeout_seconds=60,
        allowed_repositories=["fixture"], steps=[{"name": "tests", "command": ["python", "-m", "pytest", "-q"]}])
    runner = AsyncProcessRunner(environment=dict(os.environ, PYTHONPATH=".", PYTHONDONTWRITEBYTECODE="1"),
                                virtualenv=Path(sys.executable).parent.parent)
    executor = EngineeringMissionExecutor(codex_home=tmp_path, codex_model="fixture", timeout_seconds=60,
        heartbeat_interval_seconds=1, effective_uid=lambda: 1000, process_runner=runner,
        validation_executor=CodeValidationExecutor(process_runner=runner, effective_uid=lambda: 1000))
    return executor, task, workflow, workspace


@pytest.mark.asyncio
async def test_handoff_artifact_is_retained_before_model_call_and_retry_checks_integrity(tmp_path, monkeypatch):
    from swarm_worker.executors.engineering_episode import execute_episode
    from swarm_worker.engineering_episode import EpisodeIntegrityError
    executor, task, workflow, workspace = fixture(tmp_path, '1', 1)
    contract = EngineeringMissionContract.model_validate(task.input_contract)
    # This test isolates artifact custody; cryptographic handoff checks have separate tests.
    monkeypatch.setattr('swarm_worker.executors.engineering_episode.verify_handoff', lambda *_: {'fixture': True})

    async def permit():
        assert (workspace.artifacts / 'accepted-method-evidence.json').read_text() == '{}'
        assert (workspace.repository / '.invariance-accepted-method-evidence.json').read_text() == '{}'
        assert executor._changed_paths(workspace) == []
        return {'allowed': False, 'recovery_token': 'fixture-open'}

    async def heartbeat(_):
        pass

    monkeypatch.setattr('swarm_worker.executors.engineering_episode.model_capacity_permit', permit)
    for _ in range(2):
        result = await execute_episode(executor, task, contract, workflow, workspace, heartbeat)
        assert result.termination_reason == 'provider_capacity'
    artifact = workspace.artifacts / 'accepted-method-evidence.json'
    assert artifact.stat().st_mode & 0o777 == 0o600
    readable = workspace.repository / '.invariance-accepted-method-evidence.json'
    assert readable.stat().st_mode & 0o777 == 0o400
    readable.chmod(0o600)
    readable.write_text('{"tampered":true}')
    from swarm_worker.executors.code_validation import ExecutionPolicyError
    with pytest.raises(ExecutionPolicyError, match='evidence was altered'):
        executor._changed_paths(workspace)
    readable.write_text('{}')
    artifact.write_text('{"tampered":true}')
    with pytest.raises(EpisodeIntegrityError, match='evidence differs'):
        await execute_episode(executor, task, contract, workflow, workspace, heartbeat)


@pytest.mark.asyncio
async def test_episode_capacity_gate_publishes_deferral_without_authoring(tmp_path, monkeypatch):
    executor, task, workflow, workspace = fixture(tmp_path, '1', 1)
    progress = []

    async def permit():
        return {'allowed': False, 'recovery_token': 'codex:1:open'}

    async def heartbeat(value):
        progress.append(value)

    async def author(**_):
        pytest.fail('provider gate must precede author invocation')

    monkeypatch.setattr('swarm_worker.executors.engineering_episode.model_capacity_permit', permit)
    executor._run_author = author
    for _ in range(2):
        result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
        assert not result.success
        assert result.termination_reason == 'provider_capacity'
        assert result.summary['provider_capacity']['provider'] == 'codex'
        assert result.summary['engineering_episode']['model_calls'] == 0
    assert progress[-1]['status'] == 'deferred'
    assert progress[-1]['stage'] == 'author'
    assert progress[-1]['max_model_calls'] == 8
    assert progress[-1]['usage_complete'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("expression,expected", [
    ("int(2 >= 2)", 1),
    ("sum([2, 4, 6]) / 3", 4.0),
    ("[10, 20, 30][:-1]", [10, 20]),
])
async def test_real_subprocess_checks_drive_repair_and_bundle(tmp_path, expression, expected):
    executor, task, workflow, workspace = fixture(tmp_path, expression, expected)
    authors = []

    async def author(**kwargs):
        authors.append(kwargs["prompt"])
        value = "None" if len(authors) == 1 else expression
        (workspace.repository / "signal_logic.py").write_text(f"def signal():\n    return {value}\n")
        # First write must differ from the baseline, even though it is deliberately wrong.
        with (workspace.repository / "signal_logic.py").open("a") as file:
            file.write("# retained work\n")
        return step("coding-agent", kwargs["workspace"])

    async def reviewer(**kwargs):
        assert "review precedes the governed full validation" in kwargs["prompt"]
        assert "pending downstream obligations" in kwargs["prompt"]
        assert "Still reject missing required test coverage" in kwargs["prompt"]
        assert "downstream validator and bundle gates remain mandatory" in kwargs["prompt"]
        output = kwargs["workspace"].artifacts / "decision.json"
        output.write_text(json.dumps({"approved": True, "summary": "fixture review", "findings": []}))
        return step("independent-review", kwargs["workspace"])

    async def heartbeat(_):
        pass

    executor._run_author = author
    executor._run_codex = reviewer
    result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert result.success, result.model_dump()
    assert len(authors) == 2
    assert "Continue the retained implementation" in authors[1]
    assert result.summary["engineering_episode"]["repairs"] == 1
    assert (workspace.artifacts / "changes.patch").exists()
    assert (workspace.artifacts / "pr-bundle.json").exists()
    for outcome in result.steps:
        assert (workspace.plan.attempt_directory / outcome.stdout_log).exists()
    again = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert again.success
    assert len(authors) == 2


@pytest.mark.asyncio
async def test_empty_review_checks_route_retained_findings_to_author(tmp_path):
    executor, task, workflow, workspace = fixture(tmp_path, '1', 1)
    authors, reviews = [], []

    async def author(**kwargs):
        authors.append(kwargs['prompt'])
        (workspace.repository / 'signal_logic.py').write_text(
            'def signal():\n    return 1\n' + '# revised\n' * len(authors))
        return step('coding-agent', kwargs['workspace'])

    async def reviewer(**kwargs):
        assert kwargs['name'] == 'independent-review', 'Unrefuted findings must not spend adjudication'
        reviews.append(kwargs['prompt'])
        accepted = len(reviews) == 2
        (kwargs['workspace'].artifacts / 'decision.json').write_text(json.dumps({
            'approved': accepted, 'summary': 'fixture review',
            'findings': [] if accepted else [{'severity':'high',
                'message':'missing native terminal coverage ' + 'retained detail ' * 300 + 'END_OF_FINDING'}]}))
        return step('independent-review', kwargs['workspace'])

    async def heartbeat(_):
        pass

    executor._run_author, executor._run_codex = author, reviewer
    result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert result.success, result.model_dump()
    assert len(authors) == len(reviews) == 2
    assert 'missing native terminal coverage' in authors[1]
    assert 'END_OF_FINDING' in authors[1]
    assert result.summary['engineering_episode']['repairs'] == 1
    again = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert again.success and len(authors) == 2


@pytest.mark.asyncio
async def test_new_attempt_restores_partial_workspace_without_resetting_call_budget(tmp_path):
    executor, task, workflow, workspace = fixture(tmp_path, "1", 1)

    async def interrupted(**kwargs):
        (workspace.repository / "signal_logic.py").write_text("def signal():\n    return 1\n# partial\n")
        raise RuntimeError("lost worker")

    async def heartbeat(_):
        pass

    executor._run_author = interrupted
    with pytest.raises(RuntimeError, match="lost worker"):
        await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    retry_dir = workspace.plan.attempt_directory.parent / "attempt-2"
    retry_repo = retry_dir / "repository"
    retry_dir.mkdir()
    subprocess.run(["git", "worktree", "add", "--detach", str(retry_repo), workspace.metadata.resolved_base_commit],
                   cwd=workspace.repository, check=True, capture_output=True)
    (retry_dir / "logs").mkdir()
    (retry_dir / "artifacts").mkdir()
    retry = TaskWorkspace(replace(workspace.plan, attempt_number=2, attempt_directory=retry_dir,
        workspace_repository=retry_repo, logs_directory=retry_dir / "logs", artifacts_directory=retry_dir / "artifacts"),
        workspace.metadata.model_copy(update={"attempt_number": 2, "workspace_repository": retry_repo}))
    task.attempt_count = 2

    async def author(**kwargs):
        assert "# partial" in (retry_repo / "signal_logic.py").read_text()
        return step("coding-agent", kwargs["workspace"])

    async def reviewer(**kwargs):
        (kwargs["workspace"].artifacts / "decision.json").write_text(json.dumps({"approved": True, "summary": "fixture", "findings": []}))
        return step("independent-review", kwargs["workspace"])

    executor._run_author, executor._run_codex = author, reviewer
    result = await executor.execute(task=task, workflow=workflow, workspace=retry, heartbeat=heartbeat)
    assert result.success, result.model_dump()
    assert result.summary["engineering_episode"]["model_calls"] == 3


@pytest.mark.asyncio
async def test_repaired_test_failure_is_not_reported_as_terminal_review_failure(tmp_path):
    executor, task, workflow, workspace = fixture(tmp_path, '1', 1)
    task.input_contract['engineering_episode']['max_repairs'] = 1
    authors = []

    async def author(**kwargs):
        authors.append(kwargs['prompt'])
        value = 'None' if len(authors) == 1 else '1'
        (workspace.repository/'signal_logic.py').write_text(f'def signal():\n    return {value}\n# changed\n')
        return step('coding-agent', kwargs['workspace'])

    async def reviewer(**kwargs):
        (kwargs['workspace'].artifacts/'decision.json').write_text(json.dumps({
            'approved': False, 'summary': 'Real runner proof missing',
            'findings': [{'severity': 'high', 'message': 'Missing actual-runner coverage'}]}))
        return step('independent-review', kwargs['workspace'])

    async def heartbeat(_):
        pass

    executor._run_author, executor._run_codex = author, reviewer
    result = await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    assert not result.success
    assert result.termination_reason == 'engineering_episode_repair_budget_exhausted'
    assert any(not step.success for step in result.steps), 'Historical evidence must remain'
    assert 'failure_diagnostic' not in result.summary
    assert result.summary['engineering_episode']['terminal_step'] is None
    assert result.summary['engineering_episode']['terminal_receipt_id']
    assert result.summary['independent_review']['approved'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('tamper', [False, True])
async def test_session_retry_relocates_only_verified_code_and_completes_review(tmp_path, monkeypatch, tamper):
    from swarm_worker.engineering_episode import EpisodeIntegrityError
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE', 'subscription')
    executor, task, workflow, workspace = fixture(tmp_path, '1', 1)
    task.input_contract['evidence_context'] = json.dumps({'author_continuity': 'session'})
    authors = []

    async def codex(**kwargs):
        ws = kwargs['workspace']
        if kwargs['name'] == 'coding-agent':
            authors.append(kwargs)
            value = 'None' if len(authors) == 1 else '1'
            (ws.repository/'signal_logic.py').write_text(f'def signal():\n    return {value}\n# retained\n')
            result = step('coding-agent', ws)
            (ws.logs/'coding-agent.stdout.log').write_text(json.dumps({
                'type': 'thread.started', 'thread_id': '11111111-1111-4111-8111-111111111111'}))
            return result
        (ws.artifacts/'decision.json').write_text(json.dumps({
            'approved': True, 'summary': 'independent fixture review', 'findings': []}))
        return step('independent-review', ws)

    async def heartbeat(_):
        pass

    bounded = executor._run_bounded_command

    async def interrupt(**kwargs):
        raise RuntimeError('worker interrupted after durable author completion')

    executor._run_codex = codex
    executor._run_bounded_command = interrupt
    with pytest.raises(RuntimeError, match='worker interrupted'):
        await executor.execute(task=task, workflow=workflow, workspace=workspace, heartbeat=heartbeat)
    retry_dir = workspace.plan.attempt_directory.parent/'attempt-2'
    retry_repo = retry_dir/'repository'
    retry_dir.mkdir()
    subprocess.run(['git', 'worktree', 'add', '--detach', str(retry_repo), workspace.metadata.resolved_base_commit],
                   cwd=workspace.repository, check=True, capture_output=True)
    (retry_dir/'logs').mkdir()
    (retry_dir/'artifacts').mkdir()
    retry = TaskWorkspace(replace(workspace.plan, attempt_number=2, attempt_directory=retry_dir,
        workspace_repository=retry_repo, logs_directory=retry_dir/'logs', artifacts_directory=retry_dir/'artifacts'),
        workspace.metadata.model_copy(update={'attempt_number': 2, 'workspace_repository': retry_repo}))
    executor._run_bounded_command = bounded
    task.attempt_count = 2
    if tamper:
        (workspace.repository/'signal_logic.py').write_text('def signal():\n    return 999\n')
        with pytest.raises(EpisodeIntegrityError, match='differs from checkpoint'):
            await executor.execute(task=task, workflow=workflow, workspace=retry, heartbeat=heartbeat)
        assert len(authors) == 1
        return
    result = await executor.execute(task=task, workflow=workflow, workspace=retry, heartbeat=heartbeat)
    assert result.success, result.model_dump()
    assert len(authors) == 2
    assert authors[1]['workspace'].repository == retry_repo
    assert 'resume' in authors[1]['args']
    assert authors[1]['args'][authors[1]['args'].index('--cd')+1] == str(retry_repo)
    state = json.loads((retry_dir.parent/'engineering-episode/state.json').read_text())['state']
    assert state['model_calls'] == 3 and state['repairs'] == 1
    assert state['author_session']['binding']['workspace'] == str(retry_repo)
    assert len(state['author_session_relocations']) == 1
