from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.method_task import EvidenceRetrievalScope, MethodTaskContract
from app.services import recovery_evidence as service
from .test_alpha_method_tasks import fixture


def response():
    object_id = str(uuid4())
    return dict(query='dependence', projection_version='hybrid-retrieval-v1.1.0',
        corpus_digest='a'*64, fusion='rrf-v1', stale=False, confidence=.5,
        abstained=False, calibration='evidence-confidence-v1', hits=[dict(
            object_id=object_id, project='systematic-research', access_class='public',
            object_schema_version='canonical-evidence-v1.0.0', scientific_type='paragraph',
            text='source evidence '*100, score=1., confidence=.5, channel_scores={},
            channel_ranks={}, citation=dict(object_id=object_id, content_digest='b'*64,
                coordinates=dict(page=2,line_start=3,line_end=8),
                replay_path='/v1/research/retrieval/objects/'+object_id+'/replay'))])


def test_search_scope_is_explicit_and_preserves_legacy_contract(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'worker/src'))
    from swarm_worker.method_task import MethodTaskContract as WorkerContract
    request = fixture()[4]
    for model in (MethodTaskContract, WorkerContract):
        assert 'retrieval_scope' not in model.model_validate(request).model_dump(mode='json')
        scoped = deepcopy(request)
        scoped['policy']['investigation_tools'] = ['search_evidence']
        with pytest.raises(ValueError, match='retrieval scope'):
            model.model_validate(scoped)
        scoped['retrieval_scope'] = {'project':'systematic-research'}
        assert model.model_validate(scoped).retrieval_scope.max_access_class == 'public'
        scoped['retrieval_scope']['max_access_class'] = 'protected'
        with pytest.raises(ValueError):
            model.model_validate(scoped)


def test_scoped_search_retains_citation_and_marks_excerpt(monkeypatch):
    original = response()
    def search(db, request, access):
        assert request.project == 'systematic-research' and request.limit == 3
        assert access.projects == frozenset({'systematic-research'})
        assert access.max_access_class == 'public' and not access.may_write
        return original
    monkeypatch.setattr(service, 'hybrid_search', search)
    result = service.retrieve_scoped_evidence(None,
        scope=EvidenceRetrievalScope(project='systematic-research', max_excerpt_chars=200),
        query='dependence', task_id=uuid4(), operation_id='c'*64)
    hit = result['hits'][0]
    assert hit['citation'] == original['hits'][0]['citation']
    assert len(hit['text']) == 200 and hit['excerpt_truncated']
    assert len(original['hits'][0]['text']) > 200
    assert not result['scientific_approval'] and not result['execution_authority']


@pytest.mark.parametrize('defect', ['project','access','citation','stale','count'])
def test_retrieval_rejects_scope_drift_and_stale_results(monkeypatch, defect):
    data = response()
    if defect == 'project': data['hits'][0]['project'] = 'other'
    if defect == 'access': data['hits'][0]['access_class'] = 'protected'
    if defect == 'citation': data['hits'][0]['citation']['object_id'] = str(uuid4())
    if defect == 'stale': data['stale'] = True
    if defect == 'count': data['hits'] *= 4
    monkeypatch.setattr(service, 'hybrid_search', lambda *_:data)
    with pytest.raises(ValueError):
        service.retrieve_scoped_evidence(None,
            scope=EvidenceRetrievalScope(project='systematic-research'), query='dependence',
            task_id=uuid4(), operation_id='c'*64)


def test_leased_search_reserves_once_replays_and_preserves_exhausted_budget(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.services import tasks, alpha_method_tasks
    request = fixture()[4]
    request['policy'].update(investigation_tools=['search_evidence'], max_tool_calls=1)
    request['retrieval_scope'] = {'project': 'systematic-research'}
    task = SimpleNamespace(id=uuid4(), task_type='alpha_method_design', input_contract=request)
    agent, db, events = SimpleNamespace(id=uuid4()), MagicMock(), []
    db.scalars.return_value.all.side_effect = lambda: list(events)
    lease = MagicMock()
    authority = MagicMock()
    monkeypatch.setattr(tasks, 'verify_task_lease', lease)
    monkeypatch.setattr(alpha_method_tasks, 'require_current_method_authority', authority)
    def append(db, task, event_type, message, **kwargs):
        events.append(SimpleNamespace(event_type=event_type, payload=kwargs['payload']))
    monkeypatch.setattr(tasks, 'append_task_event', append)
    def retrieve(*args, **kwargs):
        assert events[0].event_type == 'recovery_search_reserved'
        assert db.commit.call_count == 1
        return {'schema_version': 'fixture', 'execution_authority': False}
    search = MagicMock(side_effect=retrieve)
    monkeypatch.setattr(service, 'retrieve_scoped_evidence', search)
    def call(operation='a'*64, query='dependence'):
        return service.search_task_evidence(db, task, agent,
            lease_token='not-a-real-token', query=query, operation_id=operation)
    assert call() == call()
    assert search.call_count == 1
    assert lease.call_count == 3 and authority.call_count == 3
    with pytest.raises(HTTPException, match='identity conflict'):
        call(query='different question')
    with pytest.raises(HTTPException, match='budget exhausted'):
        call(operation='b'*64)
    events.pop()  # Interrupted after reservation: no result can be safely replayed.
    with pytest.raises(HTTPException, match='reserved'):
        call()
    assert search.call_count == 1


@pytest.mark.parametrize('failure', ['lease', 'authority', 'task_type', 'scope', 'expired_after_search'])
def test_search_never_discloses_evidence_without_current_authority(monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.services import tasks, alpha_method_tasks

    request = fixture()[4]
    if failure != 'scope':
        request['policy']['investigation_tools'] = ['search_evidence']
        request['retrieval_scope'] = {'project': 'systematic-research'}
    task = SimpleNamespace(id=uuid4(), task_type='other' if failure == 'task_type'
                           else 'alpha_method_design', input_contract=request)
    agent, db = SimpleNamespace(id=uuid4()), MagicMock()
    db.scalars.return_value.all.return_value = []
    denied = HTTPException(403, 'Expired or unauthorized')
    lease = MagicMock(side_effect=denied if failure == 'lease' else None)
    authority = MagicMock(side_effect=denied if failure == 'authority' else
                         [None, denied] if failure == 'expired_after_search' else None)
    append, retrieve = MagicMock(), MagicMock(return_value={'private': 'evidence'})
    monkeypatch.setattr(tasks, 'verify_task_lease', lease)
    monkeypatch.setattr(tasks, 'append_task_event', append)
    monkeypatch.setattr(alpha_method_tasks, 'require_current_method_authority', authority)
    monkeypatch.setattr(service, 'retrieve_scoped_evidence', retrieve)
    with pytest.raises(HTTPException):
        service.search_task_evidence(db, task, agent, lease_token='fixture-token',
                                    query='dependence', operation_id='d'*64)
    assert retrieve.call_count == (1 if failure == 'expired_after_search' else 0)
    assert not any(call.args[2] == 'recovery_search_completed' for call in append.call_args_list)
