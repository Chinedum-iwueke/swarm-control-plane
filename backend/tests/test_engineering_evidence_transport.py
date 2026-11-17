import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import zlib

import pytest

from app.contracts import engineering_evidence as backend
from app.schemas.proposal import ProposalEngineeringMissionContract

ROOT = Path(__file__).resolve().parents[2]
WORKER_PATH = ROOT / "worker/src/swarm_worker/engineering_evidence.py"
spec = importlib.util.spec_from_file_location("worker_evidence_transport", WORKER_PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def test_deployable_codec_copies_cannot_drift():
    assert Path(backend.__file__).read_bytes() == WORKER_PATH.read_bytes()


@pytest.mark.parametrize("codec", [backend, worker])
@pytest.mark.parametrize("basket", [1, 30, 100])
def test_large_evidence_roundtrip_preserves_every_field_and_digest(codec, basket):
    evidence = {
        "discovery_candidate": {
            "scientific_specification": {"equation": "alpha", "method": "frozen method " * 2000},
            "retained_candidate_recovery": {"rejected_methods": "historical evidence " * 1400},
        },
        "dataset_bindings": [{"instrument": f"ASSET{i}", "digest": str(i) * 64} for i in range(basket)],
        "authority": {"capital": False},
    }
    before = deepcopy(evidence)
    encoded = codec.encode_engineering_evidence(evidence)
    assert len(encoded.encode()) <= codec.WIRE_LIMIT
    assert json.loads(encoded)["_evidence_transport"] == codec.FORMAT
    for decoder in [backend, worker]:
        assert decoder.decode_engineering_evidence(encoded) == evidence
        assert decoder.expanded_engineering_evidence(encoded) == codec.canonical(evidence)
    assert evidence == before
    assert ProposalEngineeringMissionContract.bounded_evidence(encoded) == encoded


@pytest.mark.parametrize("codec", [backend, worker])
def test_legacy_plain_json_retains_its_shape(codec):
    evidence = {"equation": "\u03b1", "requirements": {"events": 40}, "receipt": "x" * 64}
    encoded = codec.encode_engineering_evidence(evidence)
    assert json.loads(encoded) == evidence
    assert codec.decode_engineering_evidence(encoded) == evidence


def envelope(raw):
    return json.dumps({
        "_evidence_transport": backend.FORMAT,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "expanded_bytes": len(raw),
        "payload": base64.b64encode(zlib.compress(raw)).decode(),
    })


@pytest.mark.parametrize("codec", [backend, worker])
@pytest.mark.parametrize("mutation", ["hash", "length", "format", "extra", "truncated", "trailing", "payload"])
def test_bad_envelope_rejected(codec, mutation):
    value = json.loads(envelope(b'{"method":"frozen"}'))
    if mutation == "hash": value["sha256"] = "0" * 64
    if mutation == "length": value["expanded_bytes"] += 1
    if mutation == "format": value["_evidence_transport"] = "future-v2"
    if mutation == "extra": value["authority"] = True
    if mutation == "payload": value["payload"] = "not base64!"
    if mutation in {"truncated", "trailing"}:
        raw = base64.b64decode(value["payload"])
        value["payload"] = base64.b64encode(raw[:-1] if mutation == "truncated" else raw + b"x").decode()
    with pytest.raises(ValueError):
        codec.decode_engineering_evidence(json.dumps(value))


@pytest.mark.parametrize("codec", [backend, worker])
@pytest.mark.parametrize("raw", [
    b'{"a":1,"a":2}', b'{"a":NaN}', b'[]',
    b'{"_evidence_transport":"nested"}',
    json.dumps({str(i): i for i in range(21)}).encode(),
    b'{"a":' * 34 + b'0' + b'}' * 34,
])
def test_decoded_payload_keeps_original_safety_checks(codec, raw):
    with pytest.raises(ValueError):
        codec.decode_engineering_evidence(envelope(raw))


@pytest.mark.parametrize("codec", [backend, worker])
def test_expansion_bomb_rejected_even_with_false_declared_length(codec):
    value = json.loads(envelope(b'{"a":"' + b'x' * 1_000_000 + b'"}'))
    value["expanded_bytes"] = 100
    with pytest.raises(ValueError, match="bound"):
        codec.decode_engineering_evidence(json.dumps(value))
    with pytest.raises(ValueError, match="expanded"):
        codec.encode_engineering_evidence({"a": "x" * 96_000})


@pytest.mark.parametrize("codec", [backend, worker])
def test_incompressible_payload_still_respects_wire_budget(codec):
    import random
    raw = random.Random(42).randbytes(60_000)
    with pytest.raises(ValueError, match="wire"):
        codec.encode_engineering_evidence({"a": base64.b64encode(raw).decode()})


def large_handoff():
    return {"discovery_candidate": {"question": "Frozen question"},
            "accepted_method_handoff": {
                "schema_version": "accepted-method-engineering-handoff-v1",
                "plan_evidence_digest": "plans", "handoff_digest": "test-only",
                "packet": {"proposal": {"method": "Frozen estimand"},
                           "requirements": {"support": "Preserve every minimum"},
                           "evidence": {"plans": {"smoke": "ready", "scientific": "ready"},
                                        "history": "retained provenance " * 6000}}}}


@pytest.mark.parametrize("codec", [backend, worker])
def test_large_handoff_preserves_full_evidence_and_bounds_model_view(codec):
    document = large_handoff()
    before = deepcopy(document)
    encoded = codec.encode_engineering_evidence(document)
    for decoder in [backend, worker]:
        assert decoder.decode_engineering_evidence(encoded) == before
        assert decoder.expanded_engineering_evidence(encoded) == codec.canonical(before)
        prompt = json.loads(decoder.prompt_engineering_evidence(encoded))
        context = prompt['accepted_method_context']
        assert context['proposal'] == before['accepted_method_handoff']['packet']['proposal']
        assert context['requirements'] == before['accepted_method_handoff']['packet']['requirements']
        assert context['full_evidence_sha256'] == hashlib.sha256(codec.canonical(before).encode()).hexdigest()
        assert len(codec.canonical(prompt).encode()) <= codec.EXPANDED_LIMIT
    assert document == before


@pytest.mark.parametrize("codec", [backend, worker])
def test_large_active_science_and_excessive_history_still_fail(codec):
    document = large_handoff()
    document['accepted_method_handoff']['packet']['proposal']['method'] = 'm' * 96_000
    with pytest.raises(ValueError, match='active engineering context'):
        codec.encode_engineering_evidence(document)
    document = large_handoff()
    document['accepted_method_handoff']['packet']['evidence']['history'] = 'x' * 262_144
    with pytest.raises(ValueError, match='expanded'):
        codec.encode_engineering_evidence(document)


@pytest.mark.parametrize("codec", [backend, worker])
def test_non_handoff_cannot_use_larger_decode_budget(codec):
    with pytest.raises(ValueError, match='bound'):
        codec.decode_engineering_evidence(envelope(codec.canonical({'history': 'x' * 100_000}).encode()))
    with pytest.raises(ValueError, match='reserved'):
        codec.encode_engineering_evidence({'accepted_method_context': {'spoofed': True}})


@pytest.mark.parametrize("codec", [backend, worker])
@pytest.mark.parametrize("mutation", ['trailing', 'truncated', 'hash', 'bomb'])
def test_handoff_xz_integrity_and_expansion_limits(codec, mutation):
    encoded = json.loads(codec.encode_engineering_evidence(large_handoff()))
    assert encoded['_evidence_transport'] == codec.HANDOFF_FORMAT
    payload = base64.b64decode(encoded['payload'])
    if mutation == 'trailing': payload += b'ignored'
    if mutation == 'truncated': payload = payload[:-1]
    if mutation == 'hash': encoded['sha256'] = '0' * 64
    if mutation == 'bomb': payload = lzma.compress(b'x' * 1_000_000, preset=3)
    encoded['payload'] = base64.b64encode(payload).decode()
    with pytest.raises(ValueError):
        codec.decode_engineering_evidence(json.dumps(encoded))
