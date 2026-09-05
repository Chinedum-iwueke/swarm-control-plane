from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.scientific_fidelity import (
    ScientificAdjudication,
    ScientificBenchmark,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import ScientificBenchmarkCreate
from app.services.scientific_fidelity import (
    create_benchmark,
    digest,
    evaluate_benchmark,
)

REPRESENTATION_VERSION = "scientific-fidelity-v2.1.0"
TARGETS = {"equation": 10, "table": 5, "figure": 5}


def prepare(db) -> ScientificBenchmark:
    records = list(
        db.scalars(
            select(ScientificRepresentation).where(
                ScientificRepresentation.representation_version
                == REPRESENTATION_VERSION
            )
        ).all()
    )
    available = {
        kind: sum(item.scientific_type == kind for item in records) for kind in TARGETS
    }
    missing = [kind for kind, count in available.items() if count == 0]
    if missing:
        raise RuntimeError(
            f"Cannot build stratified live benchmark; missing: {', '.join(missing)}"
        )
    per_type = {kind: min(TARGETS[kind], available[kind]) for kind in TARGETS}
    corpus_digest = digest(sorted(item.record_digest for item in records))
    return create_benchmark(
        db,
        ScientificBenchmarkCreate(
            benchmark_version="ri014-live-corpus-v1.1.0",
            representation_version=REPRESENTATION_VERSION,
            corpus_digest=corpus_digest,
            sample_seed="ri014-independent-heldout-v1",
            per_type=per_type,
            created_by="ri014-production-pilot",
        ),
    )


def report(db, benchmark: ScientificBenchmark, *, finalize: bool) -> dict:
    ids = benchmark.sampled_representation_ids
    labels = (
        list(
            db.scalars(
                select(ScientificAdjudication).where(
                    ScientificAdjudication.representation_id.in_(ids)
                )
            ).all()
        )
        if ids
        else []
    )
    decisions: dict[str, set[str]] = {}
    for label in labels:
        decisions.setdefault(str(label.representation_id), set()).add(label.decision)
    resolved = {key for key, values in decisions.items() if len(values) == 1}
    conflicts = {
        key: sorted(values) for key, values in decisions.items() if len(values) > 1
    }
    pending = sorted(set(ids) - resolved - set(conflicts))
    if finalize:
        if pending or conflicts:
            raise RuntimeError(
                f"Independent adjudication incomplete: {len(pending)} pending, {len(conflicts)} conflicted"
            )
        benchmark = evaluate_benchmark(db, benchmark.id)
    return {
        "benchmark_id": str(benchmark.id),
        "benchmark_status": benchmark.status,
        "sample_digest": benchmark.sample_digest,
        "corpus_digest": benchmark.corpus_digest,
        "sampled": len(ids),
        "adjudicated": len(resolved),
        "pending": pending,
        "conflicts": conflicts,
        "metrics": benchmark.metrics,
        "confidence_intervals": benchmark.confidence_intervals,
        "evaluation_digest": benchmark.evaluation_digest,
        "claim_boundary": "No qualification is inferred before complete independent adjudication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RI-014 A/B/C live production evidence pilot"
    )
    parser.add_argument("command", choices=("prepare", "status", "finalize"))
    args = parser.parse_args()
    with SessionLocal() as db:
        benchmark = prepare(db)
        db.flush()
        result = report(db, benchmark, finalize=args.command == "finalize")
        db.commit()
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
