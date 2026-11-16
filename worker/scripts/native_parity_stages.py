"""Offline downstream comparison of retained native authoring parity outputs."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def native(repo: Path, output: Path):
    import numpy as np
    import pandas as pd
    import yaml
    from bt.api import run_backtest
    from bt.governance.data_requirements import preflight_evidence
    from bt.hypotheses.contract import HypothesisContract

    card_path = repo / "research/hypotheses/alpha_003_btc_5m_impact_proxy_reversal.yaml"
    card = yaml.safe_load(card_path.read_text())
    report = {"synthetic_fixture": True, "scientific_certification": False,
              "capital_or_order_authority": False}
    try:
        preflight_evidence(card, source_commit="72dbd592662dc1922e9c144ef69bc58ce5f45af1")
    except Exception as error:
        report["modern_handoff"] = {"status": "blocked", "exception": type(error).__name__,
            "reason": str(error), "input_kind": "legacy_native_card_not_modern_handoff"}
    else:
        report["modern_handoff"] = {"status": "ready"}
    rng = np.random.default_rng(1776)
    count = 6000
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.0008, count)))
    frame = pd.DataFrame({"ts": pd.date_range("2024-01-01", periods=count, freq="min", tz="UTC"),
        "symbol": "BTCUSDT", "open": np.r_[close[0], close[:-1]],
        "high": close * 1.003, "low": close * 0.997, "close": close,
        "volume": 10.0, "quote_volume": rng.uniform(100000, 1000000, count)})
    frame["high"] = frame[["high", "open", "close"]].max(axis=1)
    frame["low"] = frame[["low", "open", "close"]].min(axis=1)
    data = output / "synthetic.csv"
    frame.to_csv(data, index=False)
    grid = HypothesisContract.from_yaml(card_path).materialize_grid()
    config = yaml.safe_load((repo / "configs/engine.yaml").read_text())
    config["strategy"] = {"name": "btc_5m_impact_proxy_reversal", **grid[0]["params"]}
    config_path = output / "smoke-config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    report["fixture_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    report["variant"] = grid[0]
    try:
        run = Path(run_backtest(config_path=str(config_path), data_path=str(data),
            out_dir=str(output / "runs"), run_name="synthetic-parity"))
        names = ["performance.json", "trades.csv", "equity.csv", "decisions.jsonl", "fills.jsonl"]
        artifacts = {name: {"exists": (run / name).exists(),
            "bytes": (run / name).stat().st_size if (run / name).exists() else 0} for name in names}
        trades = pd.read_csv(run / "trades.csv")
        report["native_engine"] = {"status": "completed", "run": str(run),
            "trade_count": len(trades), "artifacts": artifacts,
            "performance": json.loads((run / "performance.json").read_text())}
    except Exception as error:
        report["native_engine"] = {"status": "failed", "exception": type(error).__name__, "reason": str(error)}
    (output / "native-report.json").write_text(json.dumps(report, indent=2, default=str))


async def stages(args):
    from swarm_worker.executors.code_validation import AsyncProcessRunner
    from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
    from swarm_worker.policy import EngineeringMissionContract
    from swarm_worker.provider_capacity import detect_provider_capacity

    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH="src", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    executor = EngineeringMissionExecutor(codex_home=args.codex_home, codex_model="gpt-5.6-sol",
        timeout_seconds=600, heartbeat_interval_seconds=15,
        process_runner=AsyncProcessRunner(environment=env, virtualenv=args.venv))
    report = {"scope": "offline-native-stages", "production_mutated": False, "lanes": {}}
    for lane in ("direct", "worker"):
        repo = args.previous / lane / "repository"
        output = args.output / lane
        output.mkdir()
        logs, artifacts = output / "logs", output / "artifacts"
        logs.mkdir()
        artifacts.mkdir()
        if args.repair:
            target = repo / "src/bt/strategy/btc_5m_impact_proxy_reversal.py"
            (artifacts / "pre-repair.py").write_bytes(target.read_bytes())
            test_path = Path(__file__).resolve().parents[1] / "tests/fixtures/native_parity_semantics.py"
            frozen_test_digest = hashlib.sha256(test_path.read_bytes()).hexdigest()
            finding = (
                "Native baseline and the frozen completed-bar ATR convention include the current completed "
                "decision bucket in the 20-bucket ATR. Your code uses the previous 20 instead. "
                "The external stop test reproduces 154.4622126684921 instead of 156.3366973866988. "
                "The earlier reviewer suggestion to insert the first post-gap range conflicts with the frozen "
                "test_missing_bucket_cannot_become_a_multi_bucket_return assertion that _ranges is absent. "
                "Preserve that test; do not blindly implement the disputed suggestion."
                if lane == "direct" else
                "Native eligibility must include empirical threshold equality (>=), matching the frozen "
                "evaluator. Your > excludes ties. The external binary-ratio test reproduces zero signals "
                "where the original implementation produces signals under the actual 288-bar grid value."
            )
            repair_contract = EngineeringMissionContract(repository="bulletproof_bt", workflow="engineering-mission",
                base_ref="72dbd592662dc1922e9c144ef69bc58ce5f45af1", milestone_id="PARITY-NATIVE",
                work_item_id="bounded-repair", objective=f"Repair only the retained strategy module. {finding}",
                allowed_paths=["src/bt/strategy/btc_5m_impact_proxy_reversal.py"],
                acceptance_criteria=["All 15 frozen tests and both external semantic regression tests pass unchanged."],
                stop_conditions=["Do not alter the question, YAML, tests, or scope."],
                max_files_changed=1, max_diff_lines=100, max_duration_seconds=180)
            async def repair_heartbeat(payload):
                (artifacts / "repair-heartbeat.json").write_text(json.dumps(payload, default=str))
            repair_step = await executor._run_author(contract=repair_contract,
                prompt=executor._coding_prompt(repair_contract) + f"\nRun python -m pytest -q tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py {test_path}\nFrozen external test source:\n" + test_path.read_text(),
                workspace=SimpleNamespace(repository=repo, logs=logs, artifacts=artifacts),
                heartbeat=repair_heartbeat, heartbeat_failures=[], timeout_seconds=180)
            (artifacts / "repair-step.json").write_text(repair_step.model_dump_json(indent=2))
            if not repair_step.success:
                raise RuntimeError("Bounded author repair failed; no automatic retry")
            status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, text=True)
            if status.strip() != "?? src/bt/strategy/btc_5m_impact_proxy_reversal.py":
                raise RuntimeError("Repair modified files outside the frozen strategy scope")
            if hashlib.sha256(test_path.read_bytes()).hexdigest() != frozen_test_digest:
                raise RuntimeError("Repair modified external acceptance tests")
            with (logs / "regression-tests.log").open("w") as test_log:
                subprocess.run([str(args.venv / "bin/python"), "-m", "pytest", "-q",
                    "tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py", str(test_path)],
                    cwd=repo, env=env, stdout=test_log, stderr=subprocess.STDOUT, timeout=120, check=True)
        with (logs / "native.log").open("w") as log:
            subprocess.run([str(args.venv / "bin/python"), str(Path(__file__).resolve()),
                "--native", "--repo", str(repo), "--output", str(output)], cwd=repo, env=env,
                stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        result = json.loads((output / "native-report.json").read_text())
        report["lanes"][lane] = result
        (args.output / "report.json").write_text(json.dumps(report, indent=2, default=str))
        schema = {"type": "object", "additionalProperties": False,
            "required": ["approved", "summary", "findings"], "properties": {
                "approved": {"type": "boolean"}, "summary": {"type": "string"},
                "findings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["severity", "message"], "properties": {
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "message": {"type": "string"}}}}}}
        schema_path = artifacts / "review-schema.json"
        schema_path.write_text(json.dumps(schema))
        contract = EngineeringMissionContract(repository="bulletproof_bt", workflow="engineering-mission",
            base_ref="72dbd592662dc1922e9c144ef69bc58ce5f45af1", milestone_id="PARITY-NATIVE",
            work_item_id="impact-reversal", objective="Review reconstructed strategy against the unchanged native card.",
            allowed_paths=["src/bt/strategy/btc_5m_impact_proxy_reversal.py"],
            evidence_context=json.dumps({"card_path": "research/hypotheses/alpha_003_btc_5m_impact_proxy_reversal.yaml",
                "test_path": "tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py",
                "experiment": "legacy native reconstruction, not modern ALPHA certification"}),
            acceptance_criteria=["The reconstructed module implements the frozen card's native strategy semantics.",
                "Identify concrete correctness or causality bugs even if visible tests pass.",
                "Do not demand modern handoff receipts for this legacy reconstruction experiment."],
            stop_conditions=["No changes permitted."], max_files_changed=1, max_diff_lines=2000, max_duration_seconds=600)
        workspace = SimpleNamespace(repository=repo, logs=logs, artifacts=artifacts)

        async def heartbeat(payload):
            (artifacts / "heartbeat.json").write_text(json.dumps(payload, default=str))

        step = await executor._run_codex(name="independent-review", args=["codex", "exec",
            "--ignore-user-config", "--ephemeral", "--sandbox", "read-only", "--model", "gpt-5.6-sol",
            "--output-schema", str(schema_path), "--output-last-message", str(artifacts / "review.json"), "-"],
            prompt=executor._review_prompt(contract), workspace=workspace, heartbeat=heartbeat,
            heartbeat_failures=[], timeout_seconds=600)
        result["review_process"] = step.model_dump(mode="json")
        if (artifacts / "review.json").exists():
            result["review"] = json.loads((artifacts / "review.json").read_text())
        (args.output / "report.json").write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps({"lane": lane, "engine": result["native_engine"]["status"], "review": result.get("review")}), flush=True)
        if detect_provider_capacity([step], output, {step.name: "codex"}):
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--venv", type=Path)
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args()
    if args.native:
        native(args.repo, args.output)
    else:
        asyncio.run(stages(args))
