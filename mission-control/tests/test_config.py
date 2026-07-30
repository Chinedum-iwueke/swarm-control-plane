from pathlib import Path

import pytest

from hermes_mission_control.config import MissionControlSettings


def test_settings_strip_api_slash_and_prepare(settings: MissionControlSettings) -> None:
    settings.prepare()
    assert settings.normalized_api_url == "http://control-plane.test"
    assert settings.data_root.stat().st_mode & 0o777 == 0o700


def test_non_loopback_bind_is_rejected(settings: MissionControlSettings) -> None:
    unsafe = settings.model_copy(update={"host": "0.0.0.0"})
    with pytest.raises(ValueError, match="loopback"):
        unsafe.prepare()


def test_permissive_token_file_is_rejected(
    settings: MissionControlSettings,
) -> None:
    settings.orchestrator_token_file.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        settings.prepare()


def test_empty_knowledge_roots_use_private_data_source(
    settings: MissionControlSettings,
) -> None:
    empty = settings.model_copy(update={"knowledge_roots": ""})
    empty.prepare()
    expected = (empty.data_root / "sources").resolve()
    assert empty.allowed_knowledge_roots == (expected,)
    assert expected.stat().st_mode & 0o777 == 0o700


def test_missing_configured_knowledge_root_is_rejected(
    settings: MissionControlSettings,
) -> None:
    missing = settings.model_copy(
        update={"knowledge_roots": str(settings.data_root / "missing")}
    )
    with pytest.raises(ValueError, match="unavailable"):
        missing.prepare()


def test_token_path_can_expand_home(
    settings: MissionControlSettings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert settings.read_token() == "operator-token-that-is-long-enough"
