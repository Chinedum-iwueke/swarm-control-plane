"""Trusted focused-test instrumentation, executed outside the authored package."""

# This is a coverage gate, not a scientific certification or a sandbox boundary.
# Passing still requires independent review and full Bulletproof validation.
RUNNER_PROBE_PROGRAM = r"""
import json
import ast
import faulthandler
from pathlib import Path
import sys
import pytest

runner = (Path.cwd() / "scripts/run_alpha_research_assignment.py").resolve()
harness = (Path.cwd() / "src/bt/validation/authoring_harness.py").resolve()
require_harness = "--require-terminal-harness" in sys.argv[2:]
calls = 0
completed = 0
terminal_outcomes = set()
smoke_cases = 0

# This cheap check is only a prerequisite. Runtime observation below remains the
# authority: a dead call or a mocked function cannot satisfy coverage.
if require_harness:
    tree = ast.parse(Path(sys.argv[1]).read_text())
    aliases = {item.asname or item.name: item.name
               for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               and node.module == "bt.validation.authoring_harness" for item in node.names}
    invoked = {aliases.get(node.func.id, node.func.id) if isinstance(node.func, ast.Name)
               else node.func.attr if isinstance(node.func, ast.Attribute) else ""
               for node in ast.walk(tree) if isinstance(node, ast.Call)}
    missing = sorted({"run_native_case", "run_scientific_case"} - invoked)
    if missing:
        print("NATIVE_RUNNER_COVERAGE=" + json.dumps({
            "phase": "contract_preflight", "missing_harness_calls": missing,
            "completed_runner_results": 0, "scientific_certification": False,
        }), flush=True)
        print("Native terminal harness must retain positive, negative, invalid and failed "
              "scientific evaluator cases plus a real runner smoke case. Missing explicit calls: "
              + ", ".join(missing), file=sys.stderr, flush=True)
        raise SystemExit(1)

class Progress:
    def pytest_runtest_logstart(self, nodeid, location):
        print("TEST_PROGRESS=" + json.dumps({"event": "started", "nodeid": nodeid}), flush=True)

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.failed:
            print("TEST_PROGRESS=" + json.dumps({"event": "finished", "nodeid": report.nodeid,
                  "phase": report.when, "outcome": report.outcome, "duration_seconds": report.duration}), flush=True)

def coverage():
    print("NATIVE_RUNNER_COVERAGE=" + json.dumps({
        "execute_registered_calls": calls, "completed_runner_results": completed,
        "terminal_outcomes": sorted(str(item) for item in terminal_outcomes),
        "smoke_cases": smoke_cases, "scientific_certification": False,
    }, sort_keys=True), flush=True)

def observe(frame, event, value):
    global calls, completed, smoke_cases
    if (frame.f_code.co_name == "run_scientific_case" and event == "return"
            and Path(frame.f_code.co_filename).resolve() == harness
            and isinstance(value, dict)
            and value.get("schema_version") == "offline-scientific-case-v1"
            and value.get("scientific_certification") is False
            and value.get("capital_or_order_authority") is False):
        terminal_outcomes.add(value.get("outcome"))
    if (frame.f_code.co_name == "run_native_case" and event == "return"
            and Path(frame.f_code.co_filename).resolve() == harness
            and isinstance(value, dict)
            and value.get("schema_version") == "offline-authoring-case-v1"
            and value.get("validation_mode") == "smoke"
            and value.get("scientific_certification") is False):
        smoke_cases += 1
    if frame.f_code.co_name != "execute_registered":
        return
    if Path(frame.f_code.co_filename).resolve() != runner:
        return
    if event == "call":
        calls += 1
    elif event == "return" and isinstance(value, dict):
        completed += 1
        coverage()

sys.setprofile(observe)
faulthandler.dump_traceback_later(60, repeat=True)
try:
    status = int(pytest.main(["-v", "--durations=10", sys.argv[1]], plugins=[Progress()]))
finally:
    sys.setprofile(None)
    faulthandler.cancel_dump_traceback_later()
print("NATIVE_RUNNER_COVERAGE=" + json.dumps({
    "execute_registered_calls": calls,
    "completed_runner_results": completed,
    "terminal_outcomes": sorted(str(item) for item in terminal_outcomes),
    "smoke_cases": smoke_cases,
    "scientific_certification": False,
}, sort_keys=True))
if status == 0 and completed == 0:
    print("Focused tests must complete the real execute_registered runner; "
          "direct evaluator calls, mocked runners, and exception-only tests "
          "do not satisfy native integration coverage.", file=sys.stderr)
    status = 1
if status == 0 and require_harness and (smoke_cases < 1 or terminal_outcomes != {"positive", "negative", "invalid", "failed"}):
    print("Native terminal harness must retain positive, negative, invalid and failed "
          "scientific evaluator cases plus a real runner smoke case, without weakening scientific semantics.", file=sys.stderr)
    status = 1
raise SystemExit(status)
"""
