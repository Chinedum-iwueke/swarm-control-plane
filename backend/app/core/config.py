from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def read_secret(path: str | None) -> str | None:
    if not path:
        return None

    secret_path = Path(path)
    if not secret_path.exists():
        return None

    value = secret_path.read_text(encoding="utf-8").strip()
    return value or None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Invariance Swarm Control Plane"
    app_environment: str = "production"
    app_version: str = "0.1.0"

    api_host: str = "0.0.0.0"
    api_port: int = 8787

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "swarm_control"
    postgres_user: str = "swarm_app"

    postgres_password_file: str = Field(
        default="/run/secrets/postgres_password"
    )

    redis_url: str = "redis://redis:6379/0"

    orchestrator_secret_file: str = Field(
        default="/run/secrets/orchestrator_secret"
    )

    agent_token_secret_file: str = Field(
        default="/run/secrets/agent_token_secret"
    )

    @property
    def postgres_password(self) -> str:
        value = read_secret(self.postgres_password_file)
        if value is None:
            raise RuntimeError("PostgreSQL password secret is unavailable.")
        return value

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.postgres_password)

        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def orchestrator_secret(self) -> str:
        value = read_secret(self.orchestrator_secret_file)
        if value is None:
            raise RuntimeError("Orchestrator secret is unavailable.")
        return value

    @property
    def agent_token_secret(self) -> str:
        value = read_secret(self.agent_token_secret_file)
        if value is None:
            raise RuntimeError("Agent token secret is unavailable.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
