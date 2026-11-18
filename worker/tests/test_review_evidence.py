import hashlib

import pytest

from swarm_worker.review_context import canonical, review_context
from swarm_worker.review_evidence import prepare_evidence, verify_evidence, validate_coverage


def packet():
    evidence = {"clock": "closed", "target": "fixed horizon"}
    digest = hashlib.sha256(canonical(evidence).encode()).hexdigest()
    return {"subject": {"review_scope": "method_design"}, "qualification": {
        "artifact_bundle": {"method_review_packet": {
            "requirements": {"timing": "Compare plan and source clock"},
            "evidence": {digest: evidence},
            "native_plan": {"clock": "open", "details": "x" * 110000}}}}}


def test_file_transport_preserves_contradictions_and_restart(tmp_path):
    value = packet()
    manifest = review_context(value)
    assert manifest["schema_version"] == "review-context-file-v1"
    assert len(canonical(manifest).encode()) < 100000
    path = prepare_evidence(tmp_path, value, manifest)
    assert path.read_text() == canonical(value)
    assert prepare_evidence(tmp_path, value, manifest) == path
    validate_coverage({"timing": manifest["evidence_digests"]}, manifest)
    for coverage in ({}, {"wrong": manifest["evidence_digests"]}, {"timing": ["fake"]}, {"timing": []}):
        with pytest.raises(ValueError):
            validate_coverage(coverage, manifest)
    path.chmod(0o600)
    path.write_text('{}')
    with pytest.raises(ValueError, match="integrity"):
        prepare_evidence(tmp_path, value, manifest)


def test_missing_and_symlink_fail_closed(tmp_path):
    value = packet()
    manifest = review_context(value)
    path = tmp_path / manifest["file"]
    with pytest.raises(ValueError, match="Missing"):
        verify_evidence(path, manifest)
    path.symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match="unsafe"):
        prepare_evidence(tmp_path, value, manifest)


def test_evidence_substitution_rejected_before_model():
    value = packet()
    evidence = value['qualification']['artifact_bundle']['method_review_packet']['evidence']
    next(iter(evidence.values()))['clock'] = 'tampered'
    with pytest.raises(ValueError, match='digest mismatch'):
        review_context(value)
