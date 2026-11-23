import sys
from pathlib import Path

import pytest

from swarm_worker.engineering_episode import EpisodeIntegrityError, canonical_digest
from swarm_worker.native_diagnostic_client import NativeDiagnosticClient, referenced_catalog


def test_diagnostic_projection_retains_transitive_references_and_validates_custody():
    leaf = {'equation': 'x[t-1]'}
    leaf_key = canonical_digest(leaf)
    parent = {'definition': 'Use ' + leaf_key}
    parent_key = canonical_digest(parent)
    history = {'historical': 'not referenced'}
    catalog = {canonical_digest(v):v for v in [leaf, parent, history]}
    assert referenced_catalog({'reference':parent_key}, catalog) == {parent_key:parent, leaf_key:leaf}
    assert len(catalog) == 3
    with pytest.raises(EpisodeIntegrityError, match='custody'):
        referenced_catalog({}, catalog | {'0'*64:history})


def client(tmp_path, text):
    scripts = tmp_path/'scripts'
    scripts.mkdir()
    (scripts/'run_native_diagnostic.py').write_text(text)
    return NativeDiagnosticClient(tmp_path, Path(sys.executable), 'a'*40)


async def run(c, **kw):
    return await c.run(tool='design_adequacy_v1', subject_digest='b'*64, payload={},
                       catalog={}, work_limit=10, timeout=kw.get('timeout',2))


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ["print('{}')", "raise RuntimeError('failure')",
                                "print('x'*300000)"])
async def test_bad_native_results_fail_closed(tmp_path, text):
    with pytest.raises(EpisodeIntegrityError): await run(client(tmp_path, text))


@pytest.mark.asyncio
async def test_native_subprocess_deadline(tmp_path):
    with pytest.raises(TimeoutError):
        await run(client(tmp_path, 'import time; time.sleep(10)'), timeout=.1)


@pytest.mark.asyncio
async def test_unregistered_command_or_overbudget_calibration_not_started(tmp_path):
    c = NativeDiagnosticClient(tmp_path, Path('/does/not/exist'), 'a'*40)
    with pytest.raises(EpisodeIntegrityError, match='unregistered'):
        await c.run(tool='shell', subject_digest='b'*64, payload={}, catalog={}, work_limit=10, timeout=1)
    with pytest.raises(EpisodeIntegrityError, match='reservation'):
        await c.run(tool='residual_calibration_v1', subject_digest='b'*64,
            payload={'design':{'calibration':{'max_work_units':100}}}, catalog={}, work_limit=10, timeout=1)
