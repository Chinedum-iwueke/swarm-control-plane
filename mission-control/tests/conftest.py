from __future__ import annotations

from pathlib import Path

import pytest

from hermes_mission_control.config import MissionControlSettings


@pytest.fixture
def settings(tmp_path: Path) -> MissionControlSettings:
    token = tmp_path / "operator.token"
    token.write_text("operator-token-that-is-long-enough", encoding="utf-8")
    token.chmod(0o600)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    return MissionControlSettings(
        api_url="http://control-plane.test/",
        orchestrator_token_file=token,
        data_root=tmp_path / "data",
        knowledge_roots=str(knowledge),
    )

