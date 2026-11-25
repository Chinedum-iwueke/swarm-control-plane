import base64
from pathlib import Path
import random
import string
import zlib

import pytest

from app.contracts import research_handoff as codec


def test_worker_and_backend_codec_match():
    root = Path(__file__).parents[2]
    assert (root/'backend/app/contracts/research_handoff.py').read_bytes() == (
        root/'worker/src/swarm_worker/research_handoff.py').read_bytes()


def test_large_handoff_roundtrip_and_legacy():
    legacy = {'qualification': {'card_digest': 'a'*64}}
    assert codec.encode(legacy) == legacy
    assert codec.decode(legacy) == legacy
    document = {'execution_preparation': {'scientific_obligations': ['definition'*1000]*40}}
    encoded = codec.encode(document)
    assert encoded['_transport'] == codec.FORMAT
    assert codec.decode(encoded) == document


@pytest.mark.parametrize('change', ['hash', 'length', 'trailing', 'bomb', 'extra'])
def test_tampered_handoff_fails_closed(change):
    envelope = codec.encode({'qualification': {'evidence': 'x'*60000}})
    if change == 'hash': envelope['sha256'] = '0'*64
    elif change == 'length': envelope['expanded_bytes'] -= 1
    elif change == 'extra': envelope['authority'] = True
    elif change == 'trailing':
        envelope['payload'] = base64.b64encode(base64.b64decode(envelope['payload'])+b'junk').decode()
    else:
        envelope['payload'] = base64.b64encode(zlib.compress(b'x'*(codec.EXPANDED_LIMIT+1))).decode()
    with pytest.raises(ValueError): codec.decode(envelope)


def test_expansion_and_incompressible_wire_bounds():
    with pytest.raises(ValueError, match='expanded'):
        codec.encode({'evidence': 'x'*codec.EXPANDED_LIMIT})
    rng = random.Random(17)
    with pytest.raises(ValueError, match='wire'):
        codec.encode({'evidence': ''.join(rng.choices(string.ascii_letters, k=60000))})


def test_backend_consumers_decode_before_using_evidence():
    from app.services.alpha_campaign import _qualification_from_result, _publication_envelope_from_result
    q = {'evidence': 'x'*60000}
    handoff = codec.encode({'qualification': q, 'publication_envelope': {'receipt': 'a'*64}})
    result = {'downstream_handoff': handoff}
    assert _qualification_from_result(result) == q
    assert _publication_envelope_from_result(result) == {'receipt': 'a'*64}
