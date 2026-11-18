"""Immutable, task-local evidence transport for bounded independent reviews."""
import hashlib
import json

from swarm_worker.review_context import canonical


def verify_evidence(path, manifest):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or unsafe review evidence")
    if path.stat().st_size > 2 * manifest["byte_count"]:
        raise ValueError("Review evidence size changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    raw = canonical(value).encode()
    if len(raw) != manifest["byte_count"] or hashlib.sha256(raw).hexdigest() != manifest["original_digest"]:
        raise ValueError("Review evidence integrity mismatch")


def prepare_evidence(directory, value, manifest):
    path = directory / manifest["file"]
    # Never replace stale evidence on restart, including dangling symlinks.
    if not path.exists() and not path.is_symlink():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(canonical(value))
        path.chmod(0o400)
    verify_evidence(path, manifest)
    return path


def coverage_schema(manifest):
    return {"type": "object", "additionalProperties": False,
            "required": sorted(manifest["requirements"]),
            "properties": {key: {"type": "array", "minItems": 1, "maxItems": 16,
                "items": {"type": "string", "enum": manifest["evidence_digests"]}}
                for key in manifest["requirements"]}}


def validate_coverage(coverage, manifest):
    if not isinstance(coverage, dict) or set(coverage) != set(manifest["requirements"]):
        raise ValueError("Review coverage must identify every exact criterion")
    for digests in coverage.values():
        if (not isinstance(digests, list) or not 1 <= len(digests) <= 16
                or any(not isinstance(key, str) or key not in manifest["evidence_digests"] for key in digests)):
            raise ValueError("Review coverage requires retained evidence")
