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
    swarm_role_package_manifest: Path = Path(
        "/home/omenka/Projects/swarm-control-plane/worker/"
        "role-packages/vm1-engineering-worker/manifest.yaml"
    )
    swarm_codex_home: Path = Path("/etc/invariance-swarm/codex-worker")
    swarm_codex_model: str = "gpt-5.6-sol"
    swarm_engineering_author_provider: str = "codex"
    swarm_local_author_url: str = "http://127.0.0.1:11434"
    swarm_local_author_model: str = "qwen2.5-coder:7b"
    swarm_local_author_max_turns: int = Field(default=6, ge=2, le=30)
    swarm_local_author_num_ctx: int = Field(default=8192, ge=8192, le=131072)
    swarm_engineering_timeout_seconds: float = 1800.0
    swarm_engineering_validation_timeout_seconds: float = Field(
        default=2400.0,
        gt=0,
        le=7200,
    )
    swarm_engineering_virtualenv: Path | None = None
    request_timeout_seconds: float = 30.0

    def prepare_directories(self) -> None:
        self.swarm_workspace_root.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )
