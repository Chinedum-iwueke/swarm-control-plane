import base64
from copy import deepcopy
from pathlib import Path
import zlib

import pytest
from swarm_worker.method_result_transport import encode, decode, digest, EXPANDED_LIMIT


def fixture():
    value = {'schema_version':'method-task-result-v2', 'contract_digest':'a'*64,
             'scientific_approval':False, 'execution_authority':False,
             'synthetic':'x'*280000}
    value['result_digest'] = digest(value)
    return value


def test_lossless_bounded_roundtrip_and_mirrored_implementation():
    value = fixture()
    before = deepcopy(value)
    packed = encode(value)
    assert packed['schema_version'] == 'method-task-result-v3'
    assert decode(packed) == value == before
    root = Path(__file__).resolve().parents[2]
    assert (root/'worker/src/swarm_worker/method_result_transport.py').read_bytes() == (
        root/'backend/app/contracts/method_result_transport.py').read_bytes()


@pytest.mark.parametrize('fault', ['hash','size','trailing','bomb','binding','authority'])
def test_corrupt_or_expanding_transport_fails_closed(fault):
    packed = encode(fixture())
    if fault == 'hash': packed['expanded_digest'] = 'f'*64
    elif fault == 'size': packed['expanded_bytes'] += 1
    elif fault == 'binding': packed['contract_digest'] = 'b'*64
    elif fault == 'authority': packed['execution_authority'] = True
    elif fault == 'trailing':
        packed['payload'] = base64.b64encode(base64.b64decode(packed['payload'])+b'extra').decode()
    else:
        packed['payload'] = base64.b64encode(zlib.compress(b'x'*(EXPANDED_LIMIT+1))).decode()
    packed['result_digest'] = digest({k:v for k,v in packed.items() if k!='result_digest'})
    with pytest.raises(ValueError): decode(packed)


def test_encoder_does_not_expand_authorized_bounds():
    value = fixture()
    value['synthetic'] = 'x'*(EXPANDED_LIMIT+1)
    with pytest.raises(ValueError): encode(value)
    assert decode({'schema_version':'method-task-result-v1'}) == {'schema_version':'method-task-result-v1'}
