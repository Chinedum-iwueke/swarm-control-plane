import hashlib
from datetime import UTC, datetime

import pytest
from app.services.governance_audit import (
    GENESIS,
    SCHEMA_VERSION,
    _private_key,
    _redact,
    _validate_references,
    digest,
    verify_bundle,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException


def event(sequence, prior, version, state, resulting, occurred_at):
    value = {
        "sequence": sequence,
        "prior_export_digest": prior,
        "stream": "lifecycle-transition",
        "source_id": f"event-{sequence}",
        "occurred_at": occurred_at,
        "actor": "founder-operator",
        "action": "register" if version == 0 else "start",
        "object": {
            "type": "research-candidate",
            "id": "candidate-1",
            "digest": "a" * 64,
        },
        "policy": {
            "id": None,
            "key": "institutional-authority",
            "version": "1.0.0",
            "digest": "b" * 64,
        },
        "evidence": ["c" * 64],
        "payload": {
            "dimension": "research",
            "prior_state": state,
            "resulting_state": resulting,
            "expected_version": version,
            "resulting_version": version + 1,
            "source_record_digest": hashlib.sha256(
                f"source-{sequence}".encode()
            ).hexdigest(),
        },
        "redactions": [],
    }
    value["record_digest"] = digest(value)
    return value


def bundle(clock_disordered=False):
    first = event(1, GENESIS, 0, "proposed", "registered", "2026-08-25T12:00:02+00:00")
    second_time = (
        "2026-08-25T12:00:01+00:00" if clock_disordered else "2026-08-25T12:00:03+00:00"
    )
    second = event(2, first["record_digest"], 1, "registered", "running", second_time)
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "requested_by": "founder-operator",
        "event_count": 2,
        "policy_digests": ["b" * 64],
        "genesis_digest": GENESIS,
        "terminal_digest": second["record_digest"],
        "events": [first, second],
        "claim_boundary": "Governance reconstruction only.",
    }
    bundle_digest = digest(unsigned)
    private = _private_key("test-signing-secret-with-at-least-32-bytes")
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        **unsigned,
        "bundle_digest": bundle_digest,
        "signature": {
            "algorithm": "ed25519",
            "key_id": hashlib.sha256(public).hexdigest(),
            "public_key": public.hex(),
            "value": private.sign(bytes.fromhex(bundle_digest)).hex(),
        },
    }


def test_fresh_client_reconstructs_signed_export():
    result = verify_bundle(bundle())
    assert result["valid"] is True
    assert result["event_count"] == 2
    assert result["reconstructed"] == {
        "research-candidate:candidate-1:research": {
            "state": "running",
            "version": 2,
            "event_digest": hashlib.sha256(b"source-2").hexdigest(),
        }
    }


@pytest.mark.parametrize("mutation", ["tamper", "missing", "reorder", "signature"])
def test_integrity_failures_are_rejected(mutation):
    value = bundle()
    if mutation == "tamper":
        value["events"][0]["actor"] = "attacker"
    elif mutation == "missing":
        value["events"].pop(0)
    elif mutation == "reorder":
        value["events"].reverse()
    else:
        value["signature"]["value"] = "00" * 64
    with pytest.raises(HTTPException, match="Invalid audit export"):
        verify_bundle(value)


def test_clock_disorder_does_not_destroy_canonical_sequence():
    assert verify_bundle(bundle(clock_disordered=True))["valid"] is True


def test_sensitive_values_are_replaced_by_verifiable_receipts():
    cleaned, receipts = _redact(
        {"scope": {"api_token": "top-secret", "allowed_path": "/srv/data"}}
    )
    assert cleaned["scope"]["api_token"]["redacted"] is True
    assert cleaned["scope"]["allowed_path"] == "/srv/data"
    assert receipts == [
        {
            "path": "payload.scope.api_token",
            "value_digest": digest("top-secret"),
        }
    ]


def test_missing_cross_stream_reference_is_rejected():
    value = bundle()["events"]
    value[0]["policy"]["id"] = "missing-policy"
    with pytest.raises(ValueError, match="authority policy is missing"):
        _validate_references(value)


def test_bundle_digest_cannot_be_recomputed_without_signing_authority():
    value = bundle()
    value["events"][0]["actor"] = "attacker"
    value["events"][0]["record_digest"] = digest(
        {
            key: item
            for key, item in value["events"][0].items()
            if key != "record_digest"
        }
    )
    value["events"][1]["prior_export_digest"] = value["events"][0]["record_digest"]
    value["events"][1]["record_digest"] = digest(
        {
            key: item
            for key, item in value["events"][1].items()
            if key != "record_digest"
        }
    )
    value["terminal_digest"] = value["events"][1]["record_digest"]
    unsigned = {
        key: item
        for key, item in value.items()
        if key not in {"bundle_digest", "signature"}
    }
    value["bundle_digest"] = digest(unsigned)
    with pytest.raises(HTTPException, match="Invalid audit export"):
        verify_bundle(value)
