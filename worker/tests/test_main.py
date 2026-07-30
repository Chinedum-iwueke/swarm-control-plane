import argparse
import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from swarm_worker.__main__ import run_cli
from swarm_worker.config import WorkerSettings
from swarm_worker.daemon import EXIT_OK
from swarm_worker.models import AgentIdentity
from swarm_worker.service import NoWorkOutcome


def make_settings(tmp_path: Path) -> WorkerSettings:
    repository_root = tmp_path / "repositories"
    repository_root.mkdir()
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir(mode=0o700)
    workflow_directory = tmp_path / "workflows"
    workflow_directory.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(mode=0o700)
    source_workflows = Path(__file__).parents[1] / "workflows"
    for source_workflow in source_workflows.glob("*.yaml"):
        shutil.copy(source_workflow, workflow_directory)
    return WorkerSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token="swarm_ag_abcdef_cli-agent-token",
        swarm_repository_root=repository_root,
        swarm_workspace_root=workspace_root,
        swarm_workflow_directory=workflow_directory,
        swarm_codex_home=codex_home,
    )


def make_identity() -> AgentIdentity:
    now = datetime.now(timezone.utc)
    return AgentIdentity(
        id="11111111-1111-4111-8111-111111111111",
        slug="vm1-developer-coder",
        display_name="VM1 Developer Coder",
        role="developer",
        machine="vm1-developer",
        hermes_profile="restricted",
        runtime="hermes",
        runtime_version="1.0",
        status="idle",
        presence="online",
        capabilities=["code_validation", "git", "python", "testing"],
        heartbeat_metadata={},
        risk_ceiling=1,
        is_enabled=True,
        last_heartbeat_at=now,
        created_at=now,
        updated_at=now,
    )


class CheckAPI:
    def __init__(self) -> None:
        self.identity_calls = 0
        self.lease_calls = 0
        self.closed = False

    async def get_identity(self) -> AgentIdentity:
        self.identity_calls += 1
        return make_identity()

    async def lease_task(self, request: object) -> object:
        self.lease_calls += 1
        raise AssertionError("check must not lease")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_check_validates_without_leasing(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    api = CheckAPI()
    args = argparse.Namespace(
        command="check",
        log_level=None,
        command_log_level="INFO",
    )

    exit_code = await run_cli(
        args,
        settings_loader=lambda: settings,
        api_client_factory=lambda configured: api,
        stream=io.StringIO(),
    )

    assert exit_code == EXIT_OK
    assert api.identity_calls == 1
    assert api.lease_calls == 0
    assert api.closed is True


class OnceService:
    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self) -> NoWorkOutcome:
        self.calls += 1
        return NoWorkOutcome()


@pytest.mark.asyncio
async def test_once_runs_exactly_one_cycle(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    service = OnceService()
    args = argparse.Namespace(
        command="once",
        log_level=None,
        command_log_level="DEBUG",
    )

    exit_code = await run_cli(
        args,
        settings_loader=lambda: settings,
        service_factory=lambda configured: service,
        stream=io.StringIO(),
    )

    assert exit_code == EXIT_OK
    assert service.calls == 1
