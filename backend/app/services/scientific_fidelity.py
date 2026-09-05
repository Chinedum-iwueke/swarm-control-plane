import hashlib
import json
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import CanonicalEvidenceObject
from app.models.scientific_fidelity import (
    ScientificFidelityManifest,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificRepresentationCreate,
)


class ScientificFidelityConflict(RuntimeError):
    pass


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
