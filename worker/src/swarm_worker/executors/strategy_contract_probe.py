"""Trusted, cheap invalid-input contract check before native engine execution."""

CONTRACT_PROBE_PROGRAM = r'''
import json
from pathlib import Path
import sys
import pandas as pd
import yaml
from bt.hypotheses.contract import HypothesisContract
from scripts.run_alpha_research_assignment import (
    resolve_strategy_intent_evaluator,
    validate_strategy_intent_evaluation,
    required_observation_logging_evaluation,
    observation_only_contract,
)

root = Path.cwd().resolve()
path = (root / sys.argv[1]).resolve(strict=True)
if root not in path.parents:
    raise SystemExit("contract path escapes repository")
document = yaml.safe_load(path.read_text())
contract = HypothesisContract.from_dict(document)
immutable = document["immutable_contract"]
window = immutable["window"]
variants = contract.to_run_specs()
evaluator = resolve_strategy_intent_evaluator(document, root)
payload = validate_strategy_intent_evaluation(evaluator(
    frame=pd.DataFrame(), decision_frame=pd.DataFrame(), adaptive_frame=None,
    parameter_grid=contract.schema.parameter_grid,
    validation_start=window["start"], validation_end=window["end"],
    test_start=window["start"], test_end=window["end"],
    representation_plan_digest=document["execution_semantics"]["adaptive_representation_plan_digest"],
    immutable_contract=immutable, costs=document.get("costs", {}),
), variants)
evaluations = [*payload["selection_candidates"], payload["held_out_evaluation"]]
if (payload["selected_parameters"] is not None
        or payload["held_out_evaluation"]["held_out_evaluated"] is not False
        or any(item["outcome"] != "invalid" or item["passed"] is not False for item in evaluations)):
    raise SystemExit("empty data must retain invalid evidence without selection or held-out evaluation")
if observation_only_contract(document):
    for item in evaluations:
        report = required_observation_logging_evaluation(item, document["logging"]["required_fields"])
        if not report["passed"] or report["evidence_mode"] != "terminal_no_observation":
            raise SystemExit("invalid-input terminal logging failed: " + json.dumps(report, sort_keys=True))
print(json.dumps({"schema_version": "native-evaluator-contract-preflight-v1",
                  "variant_count": len(variants), "invalid_input_retained": True,
                  "scientific_certification": False, "capital_or_order_authority": False}))
'''
