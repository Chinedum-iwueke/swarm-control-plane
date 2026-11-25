"""Recover legacy producer provenance from an already published episode, not today's profile."""
import hashlib
import json

from sqlalchemy import select

from app.models.governance import Artifact
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.services.evaluator_routing import digest

EVENT = 'engineering_producer_evidence_imported'
UNKNOWN = 'unverified-historical-runtime'


def validate_episode(task, lease, completion, artifact, text):
    raw = text.encode('utf-8')
    if (len(raw) > 262144 or artifact.name != 'engineering-episode.json'
            or artifact.sha256 != hashlib.sha256(raw).hexdigest()
            or artifact.size_bytes != len(raw)
            or artifact.task_id != task.id or artifact.agent_id != lease.agent_id
            or artifact.attempt_number != task.attempt_count
            or lease.agent_id is None or completion.agent_id != lease.agent_id
            or any(k in lease.payload for k in ('producer_identity', 'producer_identity_digest'))
            or not lease.created_at <= artifact.created_at <= completion.created_at
            or task.status != 'succeeded'):
        raise ValueError('Published episode custody does not match the successful lease')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate episode key')
            result[key] = value
        return result
    episode = json.loads(text, object_pairs_hook=unique)
    result = completion.payload.get('result', {})
    summary = result.get('summary', {})
    handoff = summary.get('accepted_method_native_handoff', {})
    source = task.input_contract.get('base_ref')
    binding = episode.get('binding', {})
    session = episode.get('author_session', {})
    author = session.get('binding', {})
    terminal = (episode.get('events') or [{}])[-1]
    packages = {p.get('package_digest') for p in lease.payload.get('effective_authority', [])}
    if (result != task.result or result.get('success') is not True
            or result.get('workflow') != 'engineering-mission'
            or result.get('task_attempt') != task.attempt_count
            or result.get('base_commit') != source or artifact.source_commit != source
            or binding.get('task_id') != str(task.id)
            or binding.get('source_commit') != source or author.get('source') != source
            or not handoff.get('contract_digest')
            or binding.get('contract_digest') != handoff['contract_digest']
            or author.get('contract') != handoff['contract_digest']
            or episode.get('status') != 'completed' or episode.get('stage') != 'done'
            or terminal.get('stage') != 'bundle' or terminal.get('result', {}).get('status') != 'pass'
            or not terminal.get('receipt_id')
            or terminal['receipt_id'] != summary.get('engineering_episode', {}).get('terminal_receipt_id')
            or terminal.get('code_digest') != handoff.get('code_digest')
            or len(packages) != 1 or None in packages
            or not all(isinstance(author.get(k), str) and author[k] for k in ('provider', 'model', 'home'))
            or not isinstance(session.get('session_id'), str) or not session['session_id']):
        raise ValueError('Episode is not bound to the published engineering outcome')
    identity = dict(agent_id=str(lease.agent_id), package_digest=next(iter(packages)),
        provider=author['provider'], model_family=author['model'],
        machine=UNKNOWN, runtime=UNKNOWN,
        context_group='retained-author-home:' + digest(author['home']))
    proof = dict(schema_version='published-engineering-producer-resolution-v1',
        task_id=str(task.id), task_attempt=task.attempt_count, lease_event_id=lease.id,
        lease_payload_digest=digest(lease.payload), completion_event_id=completion.id,
        completion_payload_digest=digest(completion.payload), artifact_id=str(artifact.id),
        artifact_sha256=artifact.sha256, identity_digest=digest(identity),
        session_id=session['session_id'], unknown_dimensions=['machine', 'runtime'],
        claim_boundary='Worker-published episode provenance, not provider attestation. Historical machine/runtime are unknown and count as shared correlation, never separation.')
    return identity, proof


def _evidence(db, task, artifact_id):
    def event(kind):
        return db.scalar(select(TaskEvent).where(TaskEvent.task_id == task.id,
            TaskEvent.attempt_number == task.attempt_count, TaskEvent.event_type == kind)
            .order_by(TaskEvent.id.desc()).limit(1))
    lease, completion = event('task_leased'), event('task_completed')
    artifact = db.get(Artifact, artifact_id)
    if lease is None or completion is None or artifact is None:
        raise ValueError('Published lease, completion and artifact required')
    return lease, completion, artifact


def import_episode(db, task_id, artifact_id, text, actor):
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise ValueError('Task not found')
    lease, completion, artifact = _evidence(db, task, artifact_id)
    identity, proof = validate_episode(task, lease, completion, artifact, text)
    previous = db.scalar(select(TaskEvent).where(TaskEvent.task_id == task.id,
        TaskEvent.attempt_number == task.attempt_count, TaskEvent.event_type == EVENT)
        .order_by(TaskEvent.id.desc()).limit(1))
    if previous is not None:
        if (previous.payload.get('proof') != proof or previous.payload.get('identity') != identity
                or previous.payload.get('artifact_text') != text):
            raise ValueError('Conflicting historical producer evidence')
        return proof
    db.add(TaskEvent(task_id=task.id, agent_id=lease.agent_id, attempt_number=task.attempt_count,
        event_type=EVENT, message='Imported hash-verified published engineering episode; old lease unchanged.',
        payload=dict(actor=actor, artifact_id=str(artifact.id), artifact_text=text,
                     identity=identity, proof=proof)))
    return proof


def recovered_episode_identity(db, task):
    from uuid import UUID
    record = db.scalar(select(TaskEvent).where(TaskEvent.task_id == task.id,
        TaskEvent.attempt_number == task.attempt_count, TaskEvent.event_type == EVENT)
        .order_by(TaskEvent.id.desc()).limit(1))
    if record is None:
        return None
    try:
        evidence = _evidence(db, task, UUID(record.payload['artifact_id']))
        identity, proof = validate_episode(task, *evidence, record.payload['artifact_text'])
        if identity == record.payload['identity'] and proof == record.payload['proof']:
            return identity, proof | {'import_event_id': record.id}
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return None
