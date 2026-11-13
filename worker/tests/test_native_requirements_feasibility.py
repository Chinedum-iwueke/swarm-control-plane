import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from swarm_worker.executors.alpha_data_admission import AlphaDataAdmissionExecutor
from swarm_worker.policy import AlphaDataAdmissionContract


def contract():
    representation = {"instruments": ["BTCUSDT"]}
    return {
        "repository": "bulletproof_bt", "workflow": "alpha-data-admission", "base_ref": "a" * 40,
        "candidate_id": "10000000-0000-4000-8000-000000000001", "candidate_digest": "b" * 64,
        "catalog_receipt_id": "20000000-0000-4000-8000-000000000001", "catalog_receipt_digest": "c" * 64,
        "source_commit": "a" * 40, "data_root": "/home/omenka/Projects/bulletproof_bt/research_data",
        "backup_root": "/home/omenka/.local/share/invariance-swarm/alpha-data-backups",
        "assets": [{"venue": "bybit", "instrument": "BTCUSDT", "required_fields": ["close"]}],
        "authority": "no_capital_data_admission", "representation_plan": representation,
        "coverage_window": {"start": "2025-01-01", "end": "2026-01-01"},
        "feasibility_evidence": {"representation_plan": representation},
    }


def test_planning_contract_rejects_substituted_representation_and_unbounded_context():
    value = contract()
    assert AlphaDataAdmissionContract.model_validate(value).feasibility_evidence
    value["feasibility_evidence"] = {"representation_plan": {}}
    with pytest.raises(ValidationError, match="representation differs"):
        AlphaDataAdmissionContract.model_validate(value)
    value = contract()
    value["feasibility_evidence"]["unbounded"] = "x" * 64_001
    with pytest.raises(ValidationError, match="exceeds bound"):
        AlphaDataAdmissionContract.model_validate(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
async def test_planning_executor_never_invokes_admission_or_retries_failure(tmp_path, exit_code):
    for name in ("repository/scripts", "artifacts", "logs"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "repository/scripts/plan_alpha_requirements.py").write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "Path(sys.argv[sys.argv.index('--output')+1]).write_text(json.dumps({'status':'deferred'}))\n"
        f"raise SystemExit({exit_code})\n"
    )
    workspace = SimpleNamespace(artifacts=tmp_path / "artifacts", logs=tmp_path / "logs",
        repository=tmp_path / "repository", plan=SimpleNamespace(attempt_directory=tmp_path, resolved_base_commit="a" * 40))
    result = await AlphaDataAdmissionExecutor(heartbeat_interval_seconds=5, effective_uid=lambda: 1000,
        python_path=Path(sys.executable)).execute(
        task=SimpleNamespace(input_contract=contract(), attempt_count=1), workspace=workspace,
        workflow=SimpleNamespace(name="alpha-data-admission", steps=[], timeout_seconds=10), heartbeat=None)
    assert result.success is (exit_code == 0)
    assert result.retryable is False
    assert result.steps[0].name == "native-requirements-feasibility"
    assert "alpha_data_admission" not in result.summary
    if exit_code == 0:
        assert result.summary["native_requirements_feasibility"]["status"] == "deferred"
