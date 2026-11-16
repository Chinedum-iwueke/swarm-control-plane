import subprocess
import sys
from pathlib import Path

import pytest

from swarm_worker.executors.strategy_test_probe import RUNNER_PROBE_PROGRAM


@pytest.mark.parametrize(
    ("body", "test", "expected"),
    [
        ("return {}", "assert True", 1),
        ("return {}", "assert runner.execute_registered() == {}", 0),
        (
            "raise ValueError('invalid')",
            "with pytest.raises(ValueError): runner.execute_registered()",
            1,
        ),
        ("return {}", "assert runner.execute_registered() == {'wrong': True}", 1),
        (
            "return {}",
            "runner.execute_registered = lambda: {}; assert runner.execute_registered() == {}",
            1,
        ),
    ],
)
def test_native_runner_coverage_gate(
    tmp_path: Path, body: str, test: str, expected: int
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_alpha_research_assignment.py").write_text(
        f"def execute_registered():\n    {body}\n"
    )
    (tmp_path / "test_native.py").write_text(
        "import importlib.util\nimport pytest\n"
        "spec = importlib.util.spec_from_file_location('runner', "
        "'scripts/run_alpha_research_assignment.py')\n"
        "runner = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(runner)\n"
        f"def test_runner():\n    {test}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", RUNNER_PROBE_PROGRAM, "test_native.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    assert "NATIVE_RUNNER_COVERAGE=" in result.stdout
    if expected and "wrong" not in test:
        assert "must complete the real execute_registered" in result.stderr


def test_strict_harness_rejects_runner_only_completion(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_alpha_research_assignment.py").write_text(
        "def execute_registered():\n    return {}\n"
    )
    (tmp_path / "test_native.py").write_text(
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location('runner', 'scripts/run_alpha_research_assignment.py')\n"
        "runner = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(runner)\n"
        "def test_runner():\n    assert runner.execute_registered() == {}\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            RUNNER_PROBE_PROGRAM,
            "test_native.py",
            "--require-terminal-harness",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 1
    assert '"completed_runner_results": 0' in result.stdout
    assert '"phase": "contract_preflight"' in result.stdout
    assert "must retain positive, negative, invalid and failed" in result.stderr


@pytest.mark.parametrize("omit", [None, "positive", "negative", "invalid", "failed"])
def test_strict_harness_requires_all_successful_case_returns(
    tmp_path: Path, omit
) -> None:
    """Instrument toy functions only; this is not native scientific evidence."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_alpha_research_assignment.py").write_text(
        "def execute_registered():\n    return {}\n"
    )
    harness = tmp_path / "src/bt/validation/authoring_harness.py"
    harness.parent.mkdir(parents=True)
    harness.write_text(
        "def run_scientific_case(outcome):\n"
        "    return {'schema_version': 'offline-scientific-case-v1',\n"
        "            'scientific_certification': False,\n"
        "            'capital_or_order_authority': False, 'outcome': outcome}\n"
        "def run_native_case():\n"
        "    return {'schema_version': 'offline-authoring-case-v1',\n"
        "            'validation_mode': 'smoke', 'scientific_certification': False}\n"
    )
    outcomes = [x for x in ("positive", "negative", "invalid", "failed") if x != omit]
    (tmp_path / "test_native.py").write_text(
        "import importlib.util\n"
        "def load(name, path):\n"
        "    spec = importlib.util.spec_from_file_location(name, path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n"
        "runner = load('runner', 'scripts/run_alpha_research_assignment.py')\n"
        "harness = load('harness', 'src/bt/validation/authoring_harness.py')\n"
        "def test_runner():\n"
        "    assert runner.execute_registered() == {}\n"
        "    assert harness.run_native_case()['validation_mode'] == 'smoke'\n"
        f"    for outcome in {outcomes!r}:\n"
        "        assert harness.run_scientific_case(outcome)['outcome'] == outcome\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            RUNNER_PROBE_PROGRAM,
            "test_native.py",
            "--require-terminal-harness",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == (0 if omit is None else 1), (
        result.stdout + result.stderr
    )
    assert "TEST_PROGRESS=" in result.stdout


def test_missing_harness_fails_before_importing_expensive_tests(tmp_path):
    (tmp_path / "expensive.py").write_text(
        "from pathlib import Path\nPath('should-not-exist').write_text('imported')\n"
        "def test_incomplete():\n    assert True\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", RUNNER_PROBE_PROGRAM, "expensive.py", "--require-terminal-harness"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 1
    assert not (tmp_path / "should-not-exist").exists()
    assert "missing_harness_calls" in result.stdout


@pytest.mark.parametrize("phase", ["unit", "smoke", "scientific"])
@pytest.mark.parametrize("wrong_phase", [False, True])
def test_separate_stages_enforce_runtime_boundaries(tmp_path, phase, wrong_phase):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_alpha_research_assignment.py").write_text(
        "def execute_registered():\n    return {}\n"
    )
    harness = tmp_path / "src/bt/validation/authoring_harness.py"
    harness.parent.mkdir(parents=True)
    harness.write_text(
        "def run_native_case():\n"
        "    return {'schema_version': 'offline-authoring-case-v1', 'validation_mode': 'smoke', 'scientific_certification': False}\n"
        "def run_scientific_case(outcome):\n"
        "    return {'schema_version': 'offline-scientific-case-v1', 'outcome': outcome, 'scientific_certification': False, 'capital_or_order_authority': False}\n"
    )
    wrong_call = {
        "unit": "runner.execute_registered()",
        "smoke": "harness.run_scientific_case('positive')",
        "scientific": "runner.execute_registered()",
    }[phase]
    (tmp_path / "test_stages.py").write_text(
        "import importlib.util\nimport pytest\n"
        "def load(name, path):\n"
        "    spec = importlib.util.spec_from_file_location(name, path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n    return module\n"
        "runner = load('runner', 'scripts/run_alpha_research_assignment.py')\n"
        "harness = load('harness', 'src/bt/validation/authoring_harness.py')\n"
        "def test_unit():\n    assert True\n"
        "@pytest.mark.native_smoke\n"
        "def test_smoke():\n    runner.execute_registered()\n    harness.run_native_case()\n"
        "@pytest.mark.scientific_terminal\n"
        "def test_scientific():\n"
        "    for outcome in ('positive', 'negative', 'invalid', 'failed'):\n"
        "        harness.run_scientific_case(outcome)\n"
        + (("@pytest.mark.native_smoke\n" if phase == "smoke" else
            "@pytest.mark.scientific_terminal\n" if phase == "scientific" else "")
           + f"def test_wrong():\n    {wrong_call}\n" if wrong_phase else "")
    )
    result = subprocess.run(
        [sys.executable, "-c", RUNNER_PROBE_PROGRAM, "test_stages.py",
         "--require-terminal-harness", f"--phase={phase}"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == (1 if wrong_phase else 0), result.stdout + result.stderr
    if wrong_phase:
        assert "wrong validation phase" in result.stdout


def test_progress_heartbeat_survives_pytest_capture_without_async_stack_walk(tmp_path):
    assert "dump_traceback_later" not in RUNNER_PROBE_PROGRAM
    (tmp_path / "test_wait.py").write_text(
        "import time\ndef test_wait():\n    time.sleep(0.15)\n"
    )
    program = RUNNER_PROBE_PROGRAM.replace("progress_stop.wait(60)", "progress_stop.wait(0.01)")
    result = subprocess.run(
        [sys.executable, "-c", program, "test_wait.py", "--phase=unit"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"event": "heartbeat"' in result.stdout
    assert '"nodeid": "test_wait.py::test_wait"' in result.stdout
