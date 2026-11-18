"""Lossless review-context deduplication. Keep mirrored worker/API copies identical."""
import hashlib
import json
from collections import Counter

RAW_LIMIT = 262144
CONTEXT_LIMIT = 100000
REFERENCE = "$review_ref"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def review_context(value):
    """Bound original evidence, then replace exact repeated subtrees with hash refs."""
    raw = canonical(value)
    method = value.get("subject", {}).get("review_scope") in {
        "method_design", "method_adjudication"}
    if len(raw.encode()) > (RAW_LIMIT if method else CONTEXT_LIMIT):
        raise ValueError("Review evidence exceeds the bounded contract")
    if len(raw.encode()) <= CONTEXT_LIMIT:
        return value
    counts = Counter()

    def count(item):
        if isinstance(item, dict) and REFERENCE in item:
            raise ValueError("Reserved review reference in source evidence")
        encoded = canonical(item)
        if len(encoded.encode()) >= 512:
            counts[encoded] += 1
        children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        for child in children:
            count(child)

    count(value)
    objects = {}

    def pack(item, inline=False):
        encoded = canonical(item)
        if not inline and counts[encoded] > 1:
            key = hashlib.sha256(encoded.encode()).hexdigest()
            if key not in objects:
                objects[key] = pack(item, inline=True)
            return {REFERENCE: key}
        if isinstance(item, dict):
            return {key: pack(child) for key, child in item.items()}
        if isinstance(item, list):
            return [pack(child) for child in item]
        return item

    root = pack(value)
    result = {"schema_version": "review-context-dag-v1",
              "original_digest": hashlib.sha256(raw.encode()).hexdigest(),
              "root": root, "objects": objects}
    if len(canonical(result).encode()) > CONTEXT_LIMIT:
        packet = value.get("qualification", {}).get("artifact_bundle", {}).get("method_review_packet", {})
        requirements, evidence = packet.get("requirements"), packet.get("evidence")
        if not requirements or not evidence or len(requirements) > 64:
            raise ValueError("Review context exceeds the bounded contract after lossless deduplication")
        if any(hashlib.sha256(canonical(item).encode()).hexdigest() != key
               for key, item in evidence.items()):
            raise ValueError("Review evidence digest mismatch")
        result = {"schema_version": "review-context-file-v1",
                  "original_digest": hashlib.sha256(raw.encode()).hexdigest(),
                  "byte_count": len(raw.encode()),
                  "file": "review-evidence.json",
                  "subject": value["subject"],
                  "packet_digest": hashlib.sha256(canonical(packet).encode()).hexdigest(),
                  "requirements": requirements, "evidence_digests": sorted(evidence),
                  "sections": sorted(value)}
        if len(canonical(result).encode()) > CONTEXT_LIMIT:
            raise ValueError("Review evidence index exceeds the bounded contract")
    return result
