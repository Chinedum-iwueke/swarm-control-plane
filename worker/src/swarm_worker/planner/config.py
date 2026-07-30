from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlannerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, case_sensitive=False, extra="ignore"
    )

    swarm_api_url: str
    swarm_agent_token: str = Field(min_length=20)
    swarm_agent_slug: str = "vm1-founder-intake-planner"
    swarm_machine: str = "vm1-developer"
    swarm_lease_seconds: int = 300
    swarm_task_heartbeat_seconds: float = 30.0
    swarm_poll_interval_seconds: float = 10.0
    request_timeout_seconds: float = 30.0
    swarm_codex_binary: Path = Path("/usr/bin/codex")
    swarm_codex_home: Path = Path("/etc/invariance-swarm/codex-planner")
    swarm_codex_model: str = "gpt-5.6-sol"
    swarm_planner_timeout_seconds: float = 300.0
    swarm_planner_workspace: Path = Path(
        "/home/omenka/Projects/swarm-agent-workspaces/founder-intake"
    )
    swarm_workflow_directory: Path = Path(
        "/home/omenka/Projects/swarm-control-plane/worker/workflows"
    )
    swarm_role_package_manifest: Path = Path(
        "/home/omenka/Projects/swarm-control-plane/worker/"
        "role-packages/founder-intake-planner/manifest.yaml"
    )

    def prepare(self) -> None:
        self.swarm_planner_workspace.mkdir(
            parents=True, exist_ok=True, mode=0o700
        )
