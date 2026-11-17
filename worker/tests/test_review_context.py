import hashlib
import importlib.util
from pathlib import Path

import pytest

from swarm_worker.review_context import canonical, review_context


def restore(document):
    def expand(value):
        if isinstance(value, dict) and set(value) == {'$review_ref'}:
            key = value['$review_ref']
            result = expand(document['objects'][key])
            assert hashlib.sha256(canonical(result).encode()).hexdigest() == key
            return result
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        return value
    return expand(document['root'])


def payload():
    evidence = {'text': 'evidence' * 6000, 'unicode': '\u03b1'}
    return {'subject': {'review_scope': 'method_design'},
            'card': evidence, 'packet': {'proposal': evidence, 'evidence': [evidence]}}


def test_lossless_nested_context_and_digest():
    value = payload()
    compact = review_context(value)
    assert len(canonical(value).encode()) > 100000
    assert len(canonical(compact).encode()) < 100000
    assert restore(compact) == value
    assert compact['original_digest'] == hashlib.sha256(canonical(value).encode()).hexdigest()
    assert review_context(value) == compact


def test_producer_consumer_contracts_remain_identical():
    root = Path(__file__).resolve().parents[2]
    backend = root / 'backend/app/services/review_context.py'
    worker = root / 'worker/src/swarm_worker/review_context.py'
    assert backend.read_bytes() == worker.read_bytes()
    spec = importlib.util.spec_from_file_location('api_review_context', backend)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.review_context(payload()) == review_context(payload())


def test_rejects_unique_oversize_and_unbounded_raw():
    with pytest.raises(ValueError, match='after lossless'):
        review_context({'subject': {'review_scope': 'method_design'}, 'text': 'x' * 101000})
    with pytest.raises(ValueError, match='evidence exceeds'):
        review_context({'subject': {'review_scope': 'method_design'}, 'text': 'x' * 263000})
    value = payload()
    value['subject']['review_scope'] = 'scientific_requirements'
    with pytest.raises(ValueError, match='evidence exceeds'):
        review_context(value)


def test_reserved_reference_cannot_masquerade_as_evidence():
    value = payload()
    value['untrusted'] = {'$review_ref': 'fake'}
    with pytest.raises(ValueError, match='Reserved'):
        review_context(value)


def test_small_legacy_context_is_unchanged():
    value = {'subject': {}, 'text': 'original'}
    assert review_context(value) == value
