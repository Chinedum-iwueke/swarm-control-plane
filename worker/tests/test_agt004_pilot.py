import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "agt004_pilot",
    Path(__file__).parents[1] / "scripts" / "agt004_pilot.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_remaining_promotions_supports_first_run_and_replay() -> None:
    assert MODULE.remaining_promotions("draft") == ("rehearsed", "approved", "active")
    assert MODULE.remaining_promotions("approved") == ("active",)
    assert MODULE.remaining_promotions("active") == ()


def test_remaining_promotions_rejects_terminal_or_unknown_state() -> None:
    with pytest.raises(RuntimeError, match="not activatable"):
        MODULE.remaining_promotions("retired")
