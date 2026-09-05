import hashlib
import json
import re
import unicodedata
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import CanonicalEvidenceObject
from app.models.scientific_fidelity import (
    ScientificAdjudication,
    ScientificAdjudicationEvent,
    ScientificBenchmark,
    ScientificCorrectionProposal,
    ScientificFidelityManifest,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificAdjudicationCreate,
    ScientificBenchmarkCreate,
    ScientificCorrectionCreate,
    ScientificRepresentationCreate,
)


class ScientificFidelityConflict(RuntimeError):
    pass


ZERO_DIGEST = "0" * 64
NEGATIVE_DECISIONS = {
    "material_mismatch",
    "wrong_object_class",
    "incomplete_region",
    "unsupported_notation",
    "unreadable_source",
}


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def normalize(content: str) -> str:
    return " ".join(unicodedata.normalize("NFC", content).split())


def normalize_layout(content: str) -> str:
    """Remove presentation artifacts without changing mathematical glyphs."""
    value = unicodedata.normalize("NFC", content)
    value = value.replace("ﬁ", "fi").replace("ﬂ", "fl")
    value = re.sub(r"(?<=\w)-\s*[\u0000-\u001f]*\s*(?=\w)", "", value)
    value = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f]", "", value)
    return " ".join(value.split())


def semantic_tokens(content: str) -> list[dict]:
    pattern = (
        r"[A-Za-z\u0370-\u03ff]+[₀-₉⁰-⁹]*|\d+(?:\.\d+)?|[…=+\-*/^(),:;\[\]{}∫∑√≤≥]"
    )
    return [
        {"index": index, "value": token}
        for index, token in enumerate(re.findall(pattern, content))
    ]


def expression_tree(tokens: list[dict]) -> tuple[dict, bool]:
    values = [item["value"] for item in tokens]

    def parse(items: list[str]) -> tuple[dict, bool]:
        if not items:
            return {"kind": "empty"}, False
        if len(items) == 1:
            value = items[0]
            if re.fullmatch(r"\d+(?:\.\d+)?", value):
                return {"kind": "number", "value": value}, True
            if re.fullmatch(r"[A-Za-z\u0370-\u03ff]+[₀-₉⁰-⁹]*", value):
                return {"kind": "symbol", "value": value}, True
            return {"kind": "token", "value": value}, False
        pairs = {"(": ")", "[": "]", "{": "}"}
        if items[0] in pairs and items[-1] == pairs[items[0]]:
            depth = 0
            enclosed = True
            for index, value in enumerate(items):
                depth += value in pairs
                depth -= value in pairs.values()
                if depth == 0 and index != len(items) - 1:
                    enclosed = False
                    break
            if enclosed:
                inner = items[1:-1]
                parts, start, nested = [], 0, 0
                for index, value in enumerate(inner):
                    nested += value in pairs
                    nested -= value in pairs.values()
                    if nested == 0 and value in {",", ";"}:
                        parts.append(inner[start:index])
                        start = index + 1
                parts.append(inner[start:])
                if len(parts) > 1:
                    children = [parse(part) for part in parts]
                    kind = {"{": "set", "[": "vector", "(": "tuple"}[items[0]]
                    return {
                        "kind": kind,
                        "items": [node for node, _ in children],
                    }, all(ok for _, ok in children)
                child, complete = parse(items[1:-1])
                return {
                    "kind": "group",
                    "delimiter": items[0] + items[-1],
                    "child": child,
                }, complete
        for operators in (("=", "≤", "≥"), ("+", "-"), ("*", "/"), ("^",)):
            depth = 0
            candidates = []
            for index, value in enumerate(items):
                depth += value in pairs
                depth -= value in pairs.values()
                if depth == 0 and value in operators and index > 0:
                    candidates.append(index)
            if candidates:
                index = candidates[-1] if "^" not in operators else candidates[0]
                left, left_ok = parse(items[:index])
                right, right_ok = parse(items[index + 1 :])
                return {
                    "kind": "binary",
                    "operator": items[index],
                    "left": left,
                    "right": right,
                }, left_ok and right_ok
        if items[0] in {"∫", "∑", "√"}:
            child, complete = parse(items[1:])
            return {
                "kind": "operator",
                "operator": items[0],
                "operand": child,
            }, complete
        atoms = [parse([item]) for item in items]
        if all(ok for _, ok in atoms):
            return {
                "kind": "implicit_product",
                "factors": [node for node, _ in atoms],
            }, True
        return {"kind": "lossless_tokens", "values": items}, False

    return parse(values)


def register_representation(
    db: Session, payload: ScientificRepresentationCreate
) -> ScientificRepresentation:
    source = db.get(CanonicalEvidenceObject, payload.source_object_id)
    if source is None or source.object_type != "scientific_object":
        raise ScientificFidelityConflict(
            "Source must be a canonical scientific object."
        )
    if source.payload.get("scientific_type") != payload.scientific_type:
        raise ScientificFidelityConflict(
            "Source and derived scientific types do not match."
        )
    existing = db.scalar(
        select(ScientificRepresentation).where(
            ScientificRepresentation.source_object_id == payload.source_object_id,
            ScientificRepresentation.representation_version
            == payload.representation_version,
        )
    )
    normalized = [normalize(item.content) for item in payload.parser_outputs]
    independent = {item.parser for item in payload.parser_outputs}
    methods = {item.method for item in payload.parser_outputs}
    uncertainties: list[dict] = []
    status = "accepted"
    if len(independent) < 2:
        uncertainties.append(
            {
                "kind": "parser_coverage",
                "material": True,
                "detail": "Fewer than two independent parsers.",
            }
        )
    comparable = (
        [
            tuple(item["value"] for item in semantic_tokens(value))
            for value in normalized
        ]
        if payload.scientific_type == "equation"
        else [normalize_layout(value) for value in normalized]
    )
    if len(set(comparable)) != 1:
        uncertainties.append(
            {
                "kind": "material_disagreement",
                "material": True,
                "detail": "Independent normalized outputs disagree.",
            }
        )
    if methods == {"ocr"}:
        uncertainties.append(
            {
                "kind": "ocr_only",
                "material": True,
                "detail": "OCR alone cannot establish semantic equivalence.",
            }
        )
    if any(item.confidence < 0.9 for item in payload.parser_outputs):
        uncertainties.append(
            {
                "kind": "low_confidence",
                "material": True,
                "detail": "At least one parser is below 0.90 confidence.",
            }
        )
    dimensions: dict[str, set[str]] = {}
    for unit in payload.units:
        dimensions.setdefault(unit.symbol, set()).add(unit.dimension)
    if any(len(values) > 1 for values in dimensions.values()):
        uncertainties.append(
            {
                "kind": "dimensional_conflict",
                "material": True,
                "detail": "A symbol has conflicting declared dimensions.",
            }
        )
    if uncertainties:
        status = "review_required"
    canonical = normalized[0]
    tokens = semantic_tokens(canonical)
    tree, tree_complete = (
        expression_tree(tokens)
        if payload.scientific_type == "equation"
        else (None, True)
    )
    if not tree_complete:
        uncertainties.append(
            {
                "kind": "semantic_parse_incomplete",
                "material": True,
                "detail": "Expression is lossless, but its semantic tree is incomplete.",
            }
        )
        status = "review_required"
    semantic = {
        "tokens": tokens,
        "expression_tree": tree,
        "symbols": [item.model_dump() for item in payload.symbols],
        "units": [item.model_dump() for item in payload.units],
        "table_grid": payload.table_grid,
        "figure_caption": payload.figure_caption,
        "cross_references": [str(item) for item in payload.cross_references],
        "normalization": "Unicode-NFC/whitespace-v1",
        "layout_normalized_content": normalize_layout(canonical),
    }
    material = {
        "source_object_id": str(payload.source_object_id),
        "representation_version": payload.representation_version,
        "scientific_type": payload.scientific_type,
        "status": status,
        "normalized_content": canonical,
        "semantic_payload": semantic,
        "parser_outputs": [item.model_dump() for item in payload.parser_outputs],
        "uncertainties": uncertainties,
        "source_region_digest": payload.source_region_digest,
    }
    record_digest = digest(material)
    if existing:
        if existing.record_digest != record_digest:
            raise ScientificFidelityConflict(
                "Derived representation version is immutable."
            )
        return existing
    record = ScientificRepresentation(
        **material, record_digest=record_digest, created_by=payload.created_by
    )
    db.add(record)
    db.flush()
    return record


def publish_manifest(
    db: Session, payload: FidelityManifestCreate
) -> ScientificFidelityManifest:
    records = db.scalars(
        select(ScientificRepresentation)
        .where(
            ScientificRepresentation.representation_version
            == payload.representation_version
        )
        .order_by(ScientificRepresentation.record_digest)
    ).all()
    counts = {
        "total": len(records),
        "accepted": sum(r.status == "accepted" for r in records),
        "review_required": sum(r.status == "review_required" for r in records),
    }
    required = {
        "token_precision",
        "token_recall",
        "cell_accuracy",
        "expression_replay",
        "figure_reference_replay",
    }
    missing = required - payload.metrics.keys()
    if missing:
        raise ScientificFidelityConflict(
            f"Missing fidelity metrics: {', '.join(sorted(missing))}."
        )
    qualified = (
        bool(records)
        and counts["review_required"] == 0
        and all(
            payload.metrics[key] >= payload.thresholds.get(key, 1.0) for key in required
        )
    )
    material = {
        "corpus_digest": payload.corpus_digest,
        "representation_version": payload.representation_version,
        "status": "qualified" if qualified else "not_qualified",
        "thresholds": payload.thresholds,
        "metrics": payload.metrics,
        "counts": counts,
        "representation_digests": [r.record_digest for r in records],
    }
    record_digest = digest(material)
    existing = db.scalar(
        select(ScientificFidelityManifest).where(
            ScientificFidelityManifest.record_digest == record_digest
        )
    )
    if existing:
        return existing
    record = ScientificFidelityManifest(
        **material, record_digest=record_digest, created_by=payload.created_by
    )
    db.add(record)
    db.flush()
    return record


def adjudicate_representation(
    db: Session, payload: ScientificAdjudicationCreate
) -> ScientificAdjudication:
    representation = db.get(ScientificRepresentation, payload.representation_id)
    if representation is None:
        raise ScientificFidelityConflict("Scientific representation not found.")
    independent = payload.reviewer_id != representation.created_by
    if not independent:
        raise ScientificFidelityConflict(
            "A representation producer cannot adjudicate its own output."
        )
    existing = db.scalar(
        select(ScientificAdjudication).where(
            ScientificAdjudication.representation_id == payload.representation_id,
            ScientificAdjudication.reviewer_id == payload.reviewer_id,
        )
    )
    material = {
        "representation_id": str(payload.representation_id),
        "reviewer_id": payload.reviewer_id,
        "reviewer_role": payload.reviewer_role,
        "decision": payload.decision,
        "rationale": payload.rationale,
        "gold_payload": payload.gold_payload,
        "corpus_digest": payload.corpus_digest,
        "source_region_digest": representation.source_region_digest,
        "independent_of_producer": True,
    }
    record_digest = digest(material)
    if existing:
        if existing.record_digest != record_digest:
            raise ScientificFidelityConflict(
                "Adjudication is immutable for this reviewer and representation."
            )
        return existing
    record = ScientificAdjudication(**material, record_digest=record_digest)
    db.add(record)
    db.flush()
    event_material = {
        "adjudication_id": str(record.id),
        "sequence": 1,
        "event_type": "adjudicated",
        "payload": {"decision": payload.decision},
        "previous_digest": ZERO_DIGEST,
        "actor": payload.reviewer_id,
    }
    db.add(
        ScientificAdjudicationEvent(
            **event_material, event_digest=digest(event_material)
        )
    )
    db.flush()
    return record


def _wilson(successes: int, total: int) -> dict[str, float]:
    if not total:
        return {"lower": 0.0, "upper": 1.0}
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return {"lower": max(0.0, centre - margin), "upper": min(1.0, centre + margin)}


def create_benchmark(
    db: Session, payload: ScientificBenchmarkCreate
) -> ScientificBenchmark:
    records = list(
        db.scalars(
            select(ScientificRepresentation).where(
                ScientificRepresentation.representation_version
                == payload.representation_version
            )
        ).all()
    )
    selected: list[ScientificRepresentation] = []
    for scientific_type, count in sorted(payload.per_type.items()):
        candidates = [r for r in records if r.scientific_type == scientific_type]
        if len(candidates) < count:
            raise ScientificFidelityConflict(
                f"Scientific benchmark stratum {scientific_type} requires {count} "
                f"representations but only {len(candidates)} are available."
            )
        candidates.sort(
            key=lambda r: digest({"seed": payload.sample_seed, "id": str(r.id)})
        )
        selected.extend(candidates[:count])
    ids = [str(r.id) for r in selected]
    sample_spec = {
        "per_type": payload.per_type,
        "thresholds": payload.thresholds,
        "algorithm": "sha256-stratified-v1",
    }
    material = {
        "benchmark_version": payload.benchmark_version,
        "representation_version": payload.representation_version,
        "corpus_digest": payload.corpus_digest,
        "sample_seed": payload.sample_seed,
        "sample_spec": sample_spec,
        "sampled_representation_ids": ids,
        "sample_digest": digest(ids),
        "status": "awaiting_adjudication",
        "metrics": {},
        "confidence_intervals": {},
        "counts": {"sampled": len(ids), "adjudicated": 0, "conflicted": 0},
        "adjudication_digests": [],
    }
    record_digest = digest(material)
    existing = db.scalar(
        select(ScientificBenchmark).where(
            ScientificBenchmark.record_digest == record_digest
        )
    )
    if existing:
        return existing
    record = ScientificBenchmark(
        **material, record_digest=record_digest, created_by=payload.created_by
    )
    db.add(record)
    db.flush()
    return record


def evaluate_benchmark(db: Session, benchmark_id) -> ScientificBenchmark:
    benchmark = db.get(ScientificBenchmark, benchmark_id)
    if benchmark is None:
        raise ScientificFidelityConflict("Scientific benchmark not found.")
    if benchmark.evaluation_digest:
        return benchmark
    ids = benchmark.sampled_representation_ids
    representations = (
        list(
            db.scalars(
                select(ScientificRepresentation).where(
                    ScientificRepresentation.id.in_(ids)
                )
            ).all()
        )
        if ids
        else []
    )
    adjudications = (
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
    by_rep: dict[str, list[ScientificAdjudication]] = {}
    for item in adjudications:
        by_rep.setdefault(str(item.representation_id), []).append(item)
    resolved, conflicted = {}, 0
    for rep_id, items in by_rep.items():
        decisions = {item.decision for item in items}
        if len(decisions) == 1:
            resolved[rep_id] = items[0]
        else:
            conflicted += 1
    tp = fp = fn = tn = abstentions_correct = abstentions = 0
    per_type = {
        kind: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for kind in ("equation", "table", "figure")
    }
    for rep in representations:
        label = resolved.get(str(rep.id))
        if not label:
            continue
        predicted = rep.status == "accepted"
        actual = label.decision == "equivalent"
        key = (
            "tp"
            if predicted and actual
            else "fp"
            if predicted
            else "fn"
            if actual
            else "tn"
        )
        per_type[rep.scientific_type][key] += 1
        tp += key == "tp"
        fp += key == "fp"
        fn += key == "fn"
        tn += key == "tn"
        if not predicted:
            abstentions += 1
            abstentions_correct += not actual
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    coverage = len(resolved) / len(ids) if ids else 0.0
    escape_rate = fp / (tp + fp) if tp + fp else 0.0
    metrics = {
        "class_precision": precision,
        "class_recall": recall,
        "coverage": coverage,
        "abstention_accuracy": abstentions_correct / abstentions
        if abstentions
        else 1.0,
        "escape_rate": escape_rate,
        "per_type": per_type,
    }
    intervals = {
        "class_precision": _wilson(tp, tp + fp),
        "class_recall": _wilson(tp, tp + fn),
        "coverage": _wilson(len(resolved), len(ids)),
    }
    thresholds = benchmark.sample_spec["thresholds"]
    qualified = (
        bool(ids)
        and not conflicted
        and coverage == 1.0
        and all(metrics[key] >= threshold for key, threshold in thresholds.items())
    )
    benchmark.status = (
        "qualified" if qualified else ("conflicted" if conflicted else "not_qualified")
    )
    benchmark.metrics = metrics
    benchmark.confidence_intervals = intervals
    benchmark.counts = {
        "sampled": len(ids),
        "adjudicated": len(resolved),
        "conflicted": conflicted,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }
    benchmark.adjudication_digests = sorted(
        item.record_digest for item in adjudications
    )
    benchmark.evaluation_digest = digest(
        {
            "benchmark_record_digest": benchmark.record_digest,
            "status": benchmark.status,
            "metrics": benchmark.metrics,
            "confidence_intervals": benchmark.confidence_intervals,
            "counts": benchmark.counts,
            "adjudication_digests": benchmark.adjudication_digests,
        }
    )
    return benchmark


def propose_correction(
    db: Session, payload: ScientificCorrectionCreate
) -> ScientificCorrectionProposal:
    adjudication = db.get(ScientificAdjudication, payload.adjudication_id)
    if adjudication is None:
        raise ScientificFidelityConflict("Scientific adjudication not found.")
    if adjudication.decision not in NEGATIVE_DECISIONS:
        raise ScientificFidelityConflict("Corrections require a material adjudication.")
    if payload.proposer_id == adjudication.reviewer_id:
        raise ScientificFidelityConflict(
            "The adjudicator cannot propose the correction it will evaluate."
        )
    representation = db.get(ScientificRepresentation, adjudication.representation_id)
    if (
        representation
        and payload.proposed_version == representation.representation_version
    ):
        raise ScientificFidelityConflict(
            "A correction must use a new representation version."
        )
    material = {
        "representation_id": str(adjudication.representation_id),
        "adjudication_id": str(adjudication.id),
        "proposed_version": payload.proposed_version,
        "proposed_payload": payload.proposed_payload,
        "status": "pending_approval",
        "proposer_id": payload.proposer_id,
    }
    record_digest = digest(material)
    existing = db.scalar(
        select(ScientificCorrectionProposal).where(
            ScientificCorrectionProposal.record_digest == record_digest
        )
    )
    if existing:
        return existing
    record = ScientificCorrectionProposal(
        representation_id=adjudication.representation_id,
        adjudication_id=adjudication.id,
        proposed_version=payload.proposed_version,
        proposed_payload=payload.proposed_payload,
        status="pending_approval",
        proposer_id=payload.proposer_id,
        record_digest=record_digest,
    )
    db.add(record)
    db.flush()
    return record
