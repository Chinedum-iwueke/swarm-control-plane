from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.security import require_founder_channel, require_orchestrator
from app.schemas import FounderChannelRequest


def credential(value: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


def test_founder_channel_credential_is_distinct_from_orchestrator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    founder = tmp_path / "founder"
    orchestrator = tmp_path / "orchestrator"
    founder.write_text("f" * 64)
    orchestrator.write_text("o" * 64)
    monkeypatch.setenv("FOUNDER_CHANNEL_SECRET_FILE", str(founder))
    monkeypatch.setenv("ORCHESTRATOR_SECRET_FILE", str(orchestrator))
    get_settings.cache_clear()
    require_founder_channel(credential("f" * 64))
    with pytest.raises(HTTPException):
        require_founder_channel(credential("o" * 64))
    require_orchestrator(credential("o" * 64))
    with pytest.raises(HTTPException):
        require_orchestrator(credential("f" * 64))
    get_settings.cache_clear()


def test_founder_intake_rejects_command_surface() -> None:
    with pytest.raises(ValidationError):
        FounderChannelRequest(
            kind="task",
            project="swarm-control-plane",
            title="Unsafe",
            objective="Attempt to carry an arbitrary command.",
            risk_level=0,
            acceptance_criteria=[],
            command="bash -c anything",
        )
