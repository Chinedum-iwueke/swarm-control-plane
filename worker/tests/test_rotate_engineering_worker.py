import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "rotate_engineering_worker.py"
)
SPEC = importlib.util.spec_from_file_location("rotate_engineering_worker", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_replace_environment_token_preserves_other_settings(tmp_path: Path) -> None:
    environment = tmp_path / "worker.env"
    environment.write_text(
        "SWARM_API_URL=http://control-plane\n"
        "SWARM_AGENT_TOKEN=prior-token\n"
        "SWARM_MACHINE=vm1-developer\n",
        encoding="utf-8",
    )

    result = MODULE.replace_environment_token(environment, "replacement-token")

    assert result == (
        "SWARM_API_URL=http://control-plane\n"
        "SWARM_AGENT_TOKEN=replacement-token\n"
        "SWARM_MACHINE=vm1-developer\n"
    )


def test_replace_environment_token_rejects_missing_entry(tmp_path: Path) -> None:
    environment = tmp_path / "worker.env"
    environment.write_text(
        "SWARM_API_URL=http://control-plane\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="no SWARM_AGENT_TOKEN"):
        MODULE.replace_environment_token(environment, "replacement-token")
