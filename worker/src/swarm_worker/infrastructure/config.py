from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InfrastructureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    swarm_api_url: str
    swarm_agent_token: str = Field(min_length=20)
    swarm_agent_slug: str = "vm2-infrastructure-operator"
    swarm_machine: str = "vm2-deployment"
    swarm_poll_interval_seconds: float = Field(default=10, gt=0)
    swarm_lease_seconds: int = Field(default=300, ge=60, le=1800)
    swarm_task_heartbeat_seconds: float = Field(default=30, gt=0)
    request_timeout_seconds: float = Field(default=30, gt=0)
    swarm_broker_socket: Path = Path("/run/invariance-swarm-infrastructure/broker.sock")
    swarm_infrastructure_workspace_root: Path = Path(
        "/srv/invariance/swarm/agent-workspaces/infrastructure"
    )
    swarm_infrastructure_role_manifest: Path = Path(
        "/srv/invariance/swarm/repositories/swarm-control-plane/"
        "worker/role-packages/vm2-infrastructure-operator/manifest.yaml"
    )
    swarm_infrastructure_runbook_directory: Path = Path(
        "/srv/invariance/swarm/repositories/swarm-control-plane/"
        "worker/infrastructure-runbooks"
    )
    swarm_source_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")

    def prepare_directories(self) -> None:
        self.swarm_infrastructure_workspace_root.mkdir(
            parents=True, exist_ok=True, mode=0o700
        )
        self.swarm_infrastructure_workspace_root.chmod(0o700)
