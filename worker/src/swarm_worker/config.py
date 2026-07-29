from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    swarm_api_url: str
    swarm_agent_token: str = Field(min_length=20)
    swarm_agent_slug: str = "vm1-developer-coder"
    swarm_machine: str = "vm1-developer"
    swarm_workspace_root: Path = Path("/home/omenka/Projects/swarm-agent-workspaces")
    swarm_repository_root: Path = Path("/home/omenka/Projects")
    swarm_poll_interval_seconds: float = 10.0
    swarm_agent_heartbeat_seconds: float = 30.0
    swarm_task_heartbeat_seconds: float = 30.0
    swarm_lease_seconds: int = 300
    swarm_workflow_directory: Path = Path(
        "/home/omenka/Projects/swarm-control-plane/worker/workflows"
    )
    request_timeout_seconds: float = 30.0

    def prepare_directories(self) -> None:
        self.swarm_workspace_root.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )
