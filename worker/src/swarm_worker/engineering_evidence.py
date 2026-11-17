"""Lossless bounded engineering evidence transport; mirrored in backend/worker.

The envelope is transport only, never authority. Consumers must decode before
interpreting evidence or writing native runner inputs.
"""
import base64
import hashlib
import json
import zlib

WIRE_LIMIT = 48_000
EXPANDED_LIMIT = 96_000
FORMAT = "engineering-evidence-zlib-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def validate_document(value):
    if not isinstance(value, dict) or len(value) > 20:
        raise ValueError("engineering evidence must be a bounded JSON object")
    pending = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 32:
            raise ValueError("engineering evidence nesting exceeds safe limits")
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        pending.extend((child, depth + 1) for child in children)
    canonical(value)


def _loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate engineering evidence key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("invalid engineering evidence encoding or nesting") from exc


def decode_engineering_evidence(value):
    if not isinstance(value, str) or len(value.encode()) > WIRE_LIMIT:
        raise ValueError("engineering evidence exceeds 48000 wire bytes")
    document = _loads(value)
    if isinstance(document, dict) and "_evidence_transport" in document:
        if (set(document) != {"_evidence_transport", "sha256", "expanded_bytes", "payload"}
                or document["_evidence_transport"] != FORMAT
                or type(document["expanded_bytes"]) is not int
                or not 0 < document["expanded_bytes"] <= EXPANDED_LIMIT):
            raise ValueError("invalid engineering evidence transport envelope")
        try:
            compressed = base64.b64decode(document["payload"], validate=True)
            inflater = zlib.decompressobj()
            raw = inflater.decompress(compressed, EXPANDED_LIMIT + 1)
        except (ValueError, TypeError, zlib.error) as exc:
            raise ValueError("invalid compressed engineering evidence") from exc
        if (len(raw) > EXPANDED_LIMIT or not inflater.eof
                or inflater.unused_data or inflater.unconsumed_tail
                or len(raw) != document["expanded_bytes"]
                or hashlib.sha256(raw).hexdigest() != document["sha256"]):
            raise ValueError("engineering evidence integrity or expansion bound failed")
        document = _loads(raw)
        if isinstance(document, dict) and "_evidence_transport" in document:
            raise ValueError("nested engineering evidence transport is forbidden")
    validate_document(document)
    return document


def encode_engineering_evidence(document):
    validate_document(document)
    if "_evidence_transport" in document:
        raise ValueError("reserved engineering evidence transport key")
    raw = canonical(document).encode()
    if len(raw) <= WIRE_LIMIT:
        return raw.decode()
    if len(raw) > EXPANDED_LIMIT:
        raise ValueError("engineering evidence exceeds 96000 expanded bytes")
    envelope = canonical({
        "_evidence_transport": FORMAT,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "expanded_bytes": len(raw),
        "payload": base64.b64encode(zlib.compress(raw)).decode("ascii"),
    })
    if len(envelope.encode()) > WIRE_LIMIT:
        raise ValueError("engineering evidence exceeds 48000 wire bytes")
    return envelope


def expanded_engineering_evidence(value):
    return canonical(decode_engineering_evidence(value))

