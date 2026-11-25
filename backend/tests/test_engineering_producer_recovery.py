import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.services.engineering_producer_recovery import UNKNOWN, validate_episode
from app.services import engineering_producer_recovery as recovery
from app.services.evaluator_routing import _correlation


def fixture():
    now = datetime.now(timezone.utc)
    task_id, agent_id = uuid4(), uuid4()
    summary = dict(accepted_method_native_handoff={'contract_digest':'c'*64, 'code_digest':'d'*64},
                   engineering_episode={'terminal_receipt_id':'e'*64})
    result = dict(success=True, workflow='engineering-mission', task_attempt=1,
                  base_commit='a'*40, summary=summary)
    task = NS(id=task_id, attempt_count=1, status='succeeded',
              input_contract={'base_ref':'a'*40}, result=result)
    lease = NS(id=10, agent_id=agent_id, created_at=now,
               payload={'effective_authority':[{'package_digest':'b'*64}]})
    completion = NS(id=11, agent_id=agent_id, created_at=now+timedelta(minutes=2),
                    payload={'result':result})
    episode = dict(status='completed', stage='done',
        binding={'task_id':str(task_id), 'contract_digest':'c'*64, 'source_commit':'a'*40},
        author_session={'session_id':'session-1', 'binding':dict(source='a'*40,
            contract='c'*64, provider='codex', model='model', home='/isolated/author')},
        events=[dict(stage='bundle', result={'status':'pass'}, code_digest='d'*64, receipt_id='e'*64)])
    text = json.dumps(episode)
    artifact = NS(id=uuid4(), task_id=task_id, agent_id=agent_id, attempt_number=1,
                  name='engineering-episode.json', source_commit='a'*40,
                  created_at=now+timedelta(minutes=1), size_bytes=len(text.encode()),
                  sha256=hashlib.sha256(text.encode()).hexdigest())
    return task, lease, completion, artifact, text


def test_recovers_published_not_current_identity_and_discloses_unknowns():
    args = fixture()
    identity, proof = validate_episode(*args)
    assert identity['agent_id'] == str(args[1].agent_id)
    assert identity['provider'] == 'codex'
    assert identity['machine'] == identity['runtime'] == UNKNOWN
    assert proof['artifact_sha256'] == args[3].sha256
    assert proof['unknown_dimensions'] == ['machine', 'runtime']
    assert 'producer_identity' not in args[1].payload


@pytest.mark.parametrize('field', ['hash','size','task','agent','attempt','source','time',
                                 'completion_actor','snapshot','task_state','published_result'])
def test_rejects_custody_mismatch(field):
    task, lease, completion, artifact, text = fixture()
    if field == 'hash': artifact.sha256 = 'f'*64
    elif field == 'size': artifact.size_bytes += 1
    elif field == 'task': artifact.task_id = uuid4()
    elif field == 'agent': artifact.agent_id = uuid4()
    elif field == 'attempt': artifact.attempt_number = 2
    elif field == 'source': artifact.source_commit = 'f'*40
    elif field == 'time': artifact.created_at = completion.created_at + timedelta(seconds=1)
    elif field == 'completion_actor': completion.agent_id = uuid4()
    elif field == 'snapshot': lease.payload['producer_identity_digest'] = 'f'*64
    elif field == 'task_state': task.status = 'failed'
    else: task.result = {'success':True}
    with pytest.raises(ValueError): validate_episode(task, lease, completion, artifact, text)


@pytest.mark.parametrize('field', ['binding','receipt','provider','session','status','duplicate'])
def test_rejects_invalid_published_episode_even_with_matching_hash(field):
    task, lease, completion, artifact, text = fixture()
    episode = json.loads(text)
    if field == 'binding': episode['binding']['contract_digest'] = 'f'*64
    elif field == 'receipt': episode['events'][-1]['receipt_id'] = 'f'*64
    elif field == 'provider': episode['author_session']['binding']['provider'] = ''
    elif field == 'session': episode['author_session']['session_id'] = ''
    elif field == 'status': episode['status'] = 'running'
    text = json.dumps(episode)
    if field == 'duplicate': text = text[:-1] + ',"status":"completed"}'
    artifact.size_bytes = len(text.encode())
    artifact.sha256 = hashlib.sha256(text.encode()).hexdigest()
    with pytest.raises(ValueError): validate_episode(task, lease, completion, artifact, text)


def test_unknown_correlation_is_never_counted_as_separation():
    first = dict(machine=UNKNOWN, runtime=UNKNOWN, provider='codex', model_family='model-a')
    second = dict(machine='vm2', runtime='hermes', provider='codex', model_family='model-b')
    assert _correlation(first, second)['shared_dimension_count'] == 3
    assert _correlation(second, first)['shared_dimension_count'] == 3


def test_import_is_append_only_idempotent_and_revalidated(monkeypatch):
    task, lease, completion, artifact, text = fixture()
    db = MagicMock()
    monkeypatch.setattr(recovery, '_evidence', lambda *args: (lease, completion, artifact))
    db.scalar.side_effect = [task, None]
    proof = recovery.import_episode(db, task.id, artifact.id, text, 'operator')
    record = db.add.call_args.args[0]
    record.id = 42
    assert record.event_type == recovery.EVENT
    db.add.reset_mock()
    db.scalar.side_effect = [task, record]
    assert recovery.import_episode(db, task.id, artifact.id, text, 'operator') == proof
    db.add.assert_not_called()
    db.scalar.side_effect = [record]
    assert recovery.recovered_episode_identity(db, task)[1]['import_event_id'] == 42
    artifact.sha256 = '0'*64
    db.scalar.side_effect = [record]
    assert recovery.recovered_episode_identity(db, task) is None


def test_import_refuses_conflicting_prior_proof(monkeypatch):
    task, lease, completion, artifact, text = fixture()
    db = MagicMock()
    monkeypatch.setattr(recovery, '_evidence', lambda *args: (lease, completion, artifact))
    db.scalar.side_effect = [task, NS(payload={'proof':{}})]
    with pytest.raises(ValueError, match='Conflicting'):
        recovery.import_episode(db, task.id, artifact.id, text, 'operator')
    db.add.assert_not_called()
