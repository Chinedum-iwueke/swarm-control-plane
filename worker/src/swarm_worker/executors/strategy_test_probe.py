"""Trusted focused-test instrumentation, executed outside the authored package."""

# This is a coverage gate, not a scientific certification or a sandbox boundary.
# Passing still requires independent review and full Bulletproof validation.
RUNNER_PROBE_PROGRAM = r"""
import json
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

sys.setprofile(observe)
try:
    status = int(pytest.main(["-q", sys.argv[1]]))
finally:
    sys.setprofile(None)
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
