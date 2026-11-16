import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from swarm_worker.executors.strategy_contract_probe import CONTRACT_PROBE_PROGRAM


@pytest.mark.parametrize("fault", [None, "order", "selected", "heldout", "positive", "logging"])
def test_contract_probe_rejects_inconsistent_invalid_evidence(tmp_path: Path, fault):
    """Exercise the worker protocol with toy adapters, not scientific evidence."""
    (tmp_path / "pandas.py").write_text("class DataFrame:\n    empty = True\n")
    contract = tmp_path / "bt/hypotheses/contract.py"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        "from types import SimpleNamespace\n"
        "class HypothesisContract:\n"
        "    schema = SimpleNamespace(parameter_grid={'p': (1, 2)})\n"
        "    @classmethod\n"
        "    def from_dict(cls, document): return cls()\n"
        "    def to_run_specs(self): return [{'params': {'p': 1}}, {'params': {'p': 2}}]\n"
    )
    script = tmp_path / "scripts/run_alpha_research_assignment.py"
    script.parent.mkdir()
    script.write_text(
        f"FAULT = {fault!r}\n"
        "def resolve_strategy_intent_evaluator(document, root):\n"
        "    def evaluator(**context):\n"
        "        assert context['frame'].empty and context['decision_frame'].empty\n"
        "        invalid = {'outcome': 'invalid', 'passed': False}\n"
        "        candidates = [dict(invalid, parameters={'p': x}) for x in (1, 2)]\n"
        "        if FAULT == 'order': candidates.reverse()\n"
        "        if FAULT == 'positive': candidates[0]['outcome'] = 'positive'\n"
        "        return {'selection_candidates': candidates,\n"
        "                'selected_parameters': {'p': 1} if FAULT == 'selected' else None,\n"
        "                'held_out_evaluation': dict(invalid, held_out_evaluated=FAULT == 'heldout')}\n"
        "    return evaluator\n"
        "def validate_strategy_intent_evaluation(payload, variants):\n"
        "    assert [x['parameters'] for x in payload['selection_candidates']] == [x['params'] for x in variants]\n"
        "    return payload\n"
        "def observation_only_contract(document): return True\n"
        "def required_observation_logging_evaluation(item, fields):\n"
        "    assert fields == ['decision_trace']\n"
        "    return {'passed': FAULT != 'logging', 'evidence_mode': 'terminal_no_observation'}\n"
    )
    document = tmp_path / "research/hypotheses/fixture.yaml"
    document.parent.mkdir(parents=True)
    document.write_text(json.dumps({
        "immutable_contract": {"window": {"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"}},
        "execution_semantics": {"adaptive_representation_plan_digest": "a" * 64},
        "logging": {"required_fields": ["decision_trace"]},
    }))
    result = subprocess.run(
        [sys.executable, "-c", CONTRACT_PROBE_PROGRAM, str(document.relative_to(tmp_path))],
        cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True, text=True, timeout=15,
    )
    assert (result.returncode == 0) is (fault is None), result.stdout + result.stderr
    if fault is None:
        report = json.loads(result.stdout)
        assert report["variant_count"] == 2
        assert report["scientific_certification"] is False
