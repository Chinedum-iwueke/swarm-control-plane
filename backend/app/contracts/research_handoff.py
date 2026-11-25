"""Lossless bounded research handoffs; mirrored in backend and worker."""
import base64
import hashlib
import json
import zlib

FORMAT = "research-handoff-zlib-v1"
WIRE_LIMIT = 32768
EXPANDED_LIMIT = 524288


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def decode(value):
    if not isinstance(value, dict):
        raise ValueError("Research handoff must be an object")
    if value.get("_transport") != FORMAT:
        return value
    if (set(value) != {"_transport", "expanded_bytes", "sha256", "payload"}
            or len(json.dumps(value, sort_keys=True)) > WIRE_LIMIT
            or type(value["expanded_bytes"]) is not int
            or not 0 < value["expanded_bytes"] <= EXPANDED_LIMIT):
        raise ValueError("Invalid research handoff envelope")
    try:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(base64.b64decode(value["payload"], validate=True), EXPANDED_LIMIT + 1)
    except (ValueError, TypeError, zlib.error) as exc:
        raise ValueError("Invalid research handoff compression") from exc
    if (len(raw) != value["expanded_bytes"] or len(raw) > EXPANDED_LIMIT
            or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail
            or hashlib.sha256(raw).hexdigest() != value["sha256"]):
        raise ValueError("Research handoff integrity or expansion failure")
    def pairs(items):
        result = {}
        for key, child in items:
            if key in result:
                raise ValueError("Duplicate research handoff key")
            result[key] = child
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid research handoff JSON") from exc
    if not isinstance(result, dict) or "_transport" in result or canonical(result) != raw:
        raise ValueError("Invalid research handoff document")
    return result


def encode(value):
    if not isinstance(value, dict) or "_transport" in value:
        raise ValueError("Invalid research handoff document")
    raw = canonical(value)
    if len(raw) > EXPANDED_LIMIT:
        raise ValueError("Research handoff exceeds expanded bound")
    if len(json.dumps(value, sort_keys=True)) <= WIRE_LIMIT:
        return value
    envelope = dict(_transport=FORMAT, expanded_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        payload=base64.b64encode(zlib.compress(raw)).decode("ascii"))
    if len(json.dumps(envelope, sort_keys=True)) > WIRE_LIMIT:
        raise ValueError("Research handoff exceeds wire bound")
    return envelope
