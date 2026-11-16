import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "native_authoring_parity", Path(__file__).parents[1] / "scripts/native_authoring_parity.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fixture_removes_solution_and_history_without_modifying_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name, content in [(MODULE.TARGET, "SECRET_BASELINE_IMPLEMENTATION"),
                          (MODULE.CARD, "frozen card"), (MODULE.TEST, "frozen tests")]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    MODULE.command(["git", "init", "-q"], source)
    MODULE.command(["git", "add", "."], source)
    MODULE.command(["git", "-c", "user.name=Test", "-c", "user.email=test@localhost",
                    "commit", "-qm", "Original"], source)
    commit = MODULE.command(["git", "rev-parse", "HEAD"], source).stdout.decode().strip()
    workspace = MODULE.prepare(source, commit, tmp_path / "run", "direct")
    assert not (workspace.repository / MODULE.TARGET).exists()
    assert (source / MODULE.TARGET).read_text() == "SECRET_BASELINE_IMPLEMENTATION"
    assert (workspace.repository / MODULE.CARD).read_text() == "frozen card"
    assert MODULE.command(["git", "rev-list", "--count", "HEAD"], workspace.repository).stdout.strip() == b"1"
    original = MODULE.subprocess.run(["git", "cat-file", "-e", commit],
                                    cwd=workspace.repository, capture_output=True)
    assert original.returncode != 0
    with pytest.raises(FileExistsError):
        MODULE.prepare(source, commit, tmp_path / "run", "direct")
