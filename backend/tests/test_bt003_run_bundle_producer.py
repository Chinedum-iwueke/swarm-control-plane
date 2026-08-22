from __future__ import annotations

import pytest
from app.schemas.evidence import RunPayload
from pydantic import ValidationError


def payload(**changes):
    document = {
        "kind": "run",
        "dataset_object_ids": ["11111111-1111-4111-8111-111111111111"],
        "specification_digest": "a" * 64,
        "code_digest": "b" * 64,
        "environment_digest": "c" * 64,
        "attempt": 1,
        "bundle_digest": "d" * 64,
        "bundle_manifest_digest": "e" * 64,
        "bundle_uri": f"bundle://sha256/{'d' * 64}",
    }
    document.update(changes)
    return document


def test_digest_bound_run_bundle_reference_is_accepted() -> None:
    record = RunPayload.model_validate(payload())
    assert record.bundle_uri.endswith(record.bundle_digest)


def test_partial_or_mismatched_bundle_reference_fails_closed() -> None:
    with pytest.raises(ValidationError, match="must be complete"):
        RunPayload.model_validate(payload(bundle_manifest_digest=None))
    with pytest.raises(ValidationError, match="must match"):
        RunPayload.model_validate(payload(bundle_uri=f"bundle://sha256/{'f' * 64}"))


def test_legacy_run_payload_remains_compatible() -> None:
    legacy = payload()
    for key in ("bundle_digest", "bundle_manifest_digest", "bundle_uri"):
        legacy.pop(key)
    assert RunPayload.model_validate(legacy).bundle_digest is None
