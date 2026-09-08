import hashlib
import json

from app.db.session import SessionLocal
from app.schemas.intelligence_evaluation import (
    IntelligenceResponse,
    IntelligenceRunCreate,
    IntelligenceSuiteCreate,
)
from app.services.intelligence_evaluation import evaluate_run, readiness, register_suite

DOMAINS = (
    "backtesting-validity",
    "causal-reasoning",
    "data-quality",
    "execution-science",
    "market-microstructure",
    "portfolio-construction",
    "regime-analysis",
    "reproducibility-governance",
    "risk-engineering",
    "selection-bias",
    "statistical-inference",
    "systematic-quantitative-research",
    "time-series-methods",
)
TASKS = (
    "direct_citation",
    "formula",
    "table",
    "symbol_disambiguation",
    "cross_document_synthesis",
    "contradiction",
    "temporal_supersession",
    "negative_result",
    "multi_hop",
    "no_answer",
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> int:
    corpus = sha("ri015-contract-corpus")
    projection = sha("ri015-contract-projection")
    items = []
    responses = []
    for domain in DOMAINS:
        for task in TASKS:
            key = f"{domain}:{task}"
            citation = sha(f"citation:{key}")
            claim = sha(f"claim:{key}")
            formula = sha(f"formula:{key}") if task == "formula" else None
            table = sha(f"table:{key}") if task == "table" else None
            path = (
                [sha(f"edge:{key}:1"), sha(f"edge:{key}:2")]
                if task == "multi_hop"
                else []
            )
            abstain = task == "no_answer"
            items.append(
                {
                    "item_key": key,
                    "domain": domain,
                    "task_type": task,
                    "prompt_digest": sha(f"prompt:{key}"),
                    "required_citation_digests": [] if abstain else [citation],
                    "required_answer_tokens": [] if abstain else ["supported"],
                    "supported_claim_digests": [] if abstain else [claim],
                    "formula_digest": formula,
                    "table_digest": table,
                    "path_edge_digests": path,
                    "must_abstain": abstain,
                }
            )
            responses.append(
                IntelligenceResponse(
                    item_key=key,
                    answer_tokens=[] if abstain else ["supported"],
                    citation_digests=[] if abstain else [citation],
                    claim_digests=[] if abstain else [claim],
                    formula_digest=formula,
                    table_digest=table,
                    path_edge_digests=path,
                    abstained=abstain,
                    latency_ms=100,
                )
            )
    thresholds = {
        "citation_entailment": 1.0,
        "answer_completeness": 1.0,
        "unsupported_claim_control": 1.0,
        "abstention_calibration": 1.0,
        "formula_accuracy": 1.0,
        "table_accuracy": 1.0,
        "multi_hop_validity": 1.0,
        "latency_compliance": 1.0,
        "maximum_latency_ms": 500,
        "maximum_metric_regression": 0.0,
    }
    with SessionLocal() as db:
        suite = register_suite(
            db,
            IntelligenceSuiteCreate(
                suite_version="ri015-contract-fixture-v1.0.0",
                scope="contract_fixture",
                corpus_digest=corpus,
                projection_digest=projection,
                items=items,
                thresholds=thresholds,
                created_by="ri015-fixture-author",
            ),
        )
        run = evaluate_run(
            db,
            IntelligenceRunCreate(
                suite_id=suite.id,
                corpus_digest=corpus,
                projection_digest=projection,
                model_runtime_digest=sha("deterministic-contract-runtime-v1"),
                evaluator_id="ri015-independent-fixture-evaluator",
                responses=responses,
            ),
        )
        db.commit()
        result = readiness(db)
        result.update(
            {
                "suite_id": str(suite.id),
                "run_id": str(run.id),
                "evaluated_items": len(items),
                "domain_count": len(DOMAINS),
                "action_authority": False,
            }
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
