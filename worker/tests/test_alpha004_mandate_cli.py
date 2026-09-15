import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "arguments,message",
    [
        (["--window-start", "2025-05-01T00:00:00Z"], "Supply both"),
        (
            [
                "--window-start",
                "2026-04-01T00:00:00Z",
                "--window-end",
                "2026-05-01T00:00:00Z",
            ],
            "365 days",
        ),
        (
            ["--window-start", "2025-05-01", "--window-end", "2026-05-01"],
            "require a timezone",
        ),
        (["--bulletproof-source-commit", "main"], "40-character reviewed commit"),
    ],
)
def test_mandate_override_validation_precedes_network_or_credentials(
    arguments, message
):
    script = Path(__file__).parents[1] / "scripts/alpha004_mandate.py"
    result = subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
        env={},
    )
    assert result.returncode == 2
    assert message in result.stderr
