from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupervisorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    swarm_api_url: str
    swarm_mission_supervisor_token: str = Field(min_length=32)
    swarm_supervisor_poll_interval_seconds: float = Field(default=10, ge=2, le=300)
    request_timeout_seconds: float = Field(default=30, gt=0, le=120)

    @property
    def normalized_api_url(self) -> str:
        return self.swarm_api_url.rstrip("/")
