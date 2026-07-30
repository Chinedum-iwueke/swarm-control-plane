from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MissionControlSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HERMES_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    api_url: str
    orchestrator_token_file: Path
    data_root: Path = Path.home() / "Library/Application Support/Hermes Mission Control"
    knowledge_roots: str = ""
    host: str = "127.0.0.1"
    port: int = Field(default=8790, ge=1024, le=65535)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @property
    def normalized_api_url(self) -> str:
        return self.api_url.rstrip("/")

    @property
    def allowed_knowledge_roots(self) -> tuple[Path, ...]:
        roots = []
        for value in self.knowledge_roots.split(os.pathsep):
            if value.strip():
                roots.append(Path(value).expanduser().resolve())
        return tuple(roots) or ((self.data_root / "sources").resolve(),)

    @property
    def database_path(self) -> Path:
        return self.data_root / "knowledge.sqlite3"

    def prepare(self) -> None:
        if self.host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Mission Control must bind to a loopback address.")
        token_path = self.orchestrator_token_file.expanduser()
        if not token_path.is_file():
            raise ValueError("The orchestrator token file is unavailable.")
        if token_path.stat().st_mode & 0o077:
            raise ValueError("The orchestrator token file must have mode 0600.")
        if len(token_path.read_text(encoding="utf-8").strip()) < 20:
            raise ValueError("The orchestrator token file is empty or invalid.")
        self.data_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_root.chmod(0o700)
        if not self.knowledge_roots:
            self.allowed_knowledge_roots[0].mkdir(
                parents=True, exist_ok=True, mode=0o700
            )
        for root in self.allowed_knowledge_roots:
            if not root.is_dir():
                raise ValueError(f"Knowledge root is unavailable: {root}")

    def read_token(self) -> str:
        return self.orchestrator_token_file.expanduser().read_text(
            encoding="utf-8"
        ).strip()
