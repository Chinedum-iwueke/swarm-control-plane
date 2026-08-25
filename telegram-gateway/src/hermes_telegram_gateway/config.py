from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HERMES_TELEGRAM_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    bot_token_file: Path
    founder_channel_token_file: Path
    founder_user_id: int = Field(gt=0)
    founder_chat_id: int
    api_url: str
    data_root: Path = Path("/var/lib/hermes-telegram-gateway")
    poll_timeout_seconds: int = Field(default=25, ge=5, le=50)
    notification_interval_seconds: float = Field(default=15, ge=5, le=300)
    handoff_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    retry_initial_seconds: float = Field(default=5, ge=1, le=60)
    retry_max_seconds: float = Field(default=300, ge=5, le=900)

    def prepare(self) -> None:
        for path in (self.bot_token_file, self.founder_channel_token_file):
            if not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError(f"Protected credential file is invalid: {path}")
            if len(path.read_text(encoding="utf-8").strip()) < 20:
                raise ValueError(f"Protected credential file is empty: {path}")
        self.data_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_root.chmod(0o700)

    @property
    def bot_token(self) -> str:
        return self.bot_token_file.read_text(encoding="utf-8").strip()

    @property
    def founder_channel_token(self) -> str:
        return self.founder_channel_token_file.read_text(encoding="utf-8").strip()
