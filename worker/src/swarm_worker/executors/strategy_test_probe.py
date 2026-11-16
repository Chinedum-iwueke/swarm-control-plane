"""Trusted focused-test instrumentation, executed outside the authored package."""

# This is a coverage gate, not a scientific certification or a sandbox boundary.
# Passing still requires independent review and full Bulletproof validation.
RUNNER_PROBE_PROGRAM = r"""
import json
import ast
import os
import threading
import time
from pathlib import Path
import sys
import pytest

runner = (Path.cwd() / "scripts/run_alpha_research_assignment.py").resolve()
harness = (Path.cwd() / "src/bt/validation/authoring_harness.py").resolve()
require_harness = "--require-terminal-harness" in sys.argv[2:]
phase_args = [arg.split("=", 1)[1] for arg in sys.argv[2:] if arg.startswith("--phase=")]
phase = phase_args[0] if len(phase_args) == 1 else "all"
if phase not in {"all", "unit", "smoke", "scientific"} or len(phase_args) > 1:
    raise SystemExit("invalid validation phase")
calls = 0
completed = 0
terminal_outcomes = set()
smoke_cases = 0
phase_violations = 0
current_test = None
progress_stop = threading.Event()
progress_stream = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)

def progress_heartbeat():
    started = time.monotonic()
    while not progress_stop.wait(60):
        print("TEST_PROGRESS=" + json.dumps({"event": "heartbeat", "phase": phase,
              "nodeid": current_test, "elapsed_seconds": time.monotonic() - started}),
              file=progress_stream, flush=True)

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
    def pytest_configure(self, config):
        config.addinivalue_line("markers", "native_smoke: bounded native runner integration")
        config.addinivalue_line("markers", "scientific_terminal: full-length synthetic scientific outcomes")

    def pytest_collection_modifyitems(self, config, items):
        if phase == "all":
            return
        selected, deselected = [], []
        for item in items:
            smoke = item.get_closest_marker("native_smoke") is not None
            scientific = item.get_closest_marker("scientific_terminal") is not None
            if smoke and scientific:
                raise pytest.UsageError("A test cannot belong to both native validation stages")
            stage = "smoke" if smoke else "scientific" if scientific else "unit"
            (selected if stage == phase else deselected).append(item)
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)

    def pytest_runtest_logstart(self, nodeid, location):
        global current_test
        current_test = nodeid
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
    global calls, completed, smoke_cases, phase_violations
    if (event == "call" and phase != "all" and frame.f_code.co_name in {
            "execute_registered", "run_native_case", "run_scientific_case"}):
        source = Path(frame.f_code.co_filename).resolve()
        name = frame.f_code.co_name
        if ((source == runner and name == "execute_registered" and phase != "smoke")
                or (source == harness and name == "run_native_case" and phase != "smoke")
                or (source == harness and name == "run_scientific_case" and phase != "scientific")):
            phase_violations += 1
            raise RuntimeError("Native harness invoked in the wrong validation phase: " + phase)
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

def observe_return(frame, event, value):
    if event == "return":
        observe(frame, event, value)
    return observe_return

def enter_native(frame, event, value):
    if event != "call" or frame.f_code.co_name not in {
            "execute_registered", "run_native_case", "run_scientific_case"}:
        return None
    if Path(frame.f_code.co_filename).resolve() not in {runner, harness}:
        return None
    observe(frame, event, value)
    frame.f_trace_lines = False
    frame.f_trace_opcodes = False
    return observe_return

# Only retain return tracing for native entry points. A global profiler also
# receives every C-call/return in pandas and the engine, distorting test budgets.
sys.settrace(enter_native)
# Avoid asynchronous interpreter-frame traversal: the deployed Python 3.11
# runtime crashed inside _Py_DumpTracebackThreads during profiled pandas work.
progress_thread = threading.Thread(target=progress_heartbeat, daemon=True)
progress_thread.start()
try:
    status = int(pytest.main(["-v", "--durations=10", sys.argv[1]], plugins=[Progress()]))
finally:
    sys.settrace(None)
    progress_stop.set()
    progress_thread.join(timeout=1)
print("NATIVE_RUNNER_COVERAGE=" + json.dumps({
    "phase": phase,
    "phase_violations": phase_violations,
    "execute_registered_calls": calls,
    "completed_runner_results": completed,
    "terminal_outcomes": sorted(str(item) for item in terminal_outcomes),
    "smoke_cases": smoke_cases,
    "scientific_certification": False,
}, sort_keys=True))
if phase_violations:
    status = 1
if status == 0 and phase in {"all", "smoke"} and completed == 0:
    print("Focused tests must complete the real execute_registered runner; "
          "direct evaluator calls, mocked runners, and exception-only tests "
          "do not satisfy native integration coverage.", file=sys.stderr)
    status = 1
if status == 0 and require_harness and (
        (phase in {"all", "smoke"} and smoke_cases < 1)
        or (phase in {"all", "scientific"} and terminal_outcomes != {"positive", "negative", "invalid", "failed"})):
    print("Native terminal harness must retain positive, negative, invalid and failed "
          "scientific evaluator cases plus a real runner smoke case, without weakening scientific semantics.", file=sys.stderr)
    status = 1
raise SystemExit(status)
"""
