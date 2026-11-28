"""Task-scoped evidence projection; no ingestion, model call or scientific verdict."""
from app.schemas.retrieval import HybridRetrievalRequest, HybridRetrievalResponse
from app.services.evidence import EvidenceAccessContext
from app.services.graph import digest_document
from app.services.retrieval import hybrid_search


def search_task_evidence(db, task, agent, *, lease_token, query, operation_id):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.models import TaskEvent
    from app.schemas.method_task import MethodTaskContract
    from app.services.tasks import verify_task_lease, append_task_event
    from app.services.alpha_method_tasks import require_current_method_authority
    verify_task_lease(task, agent, lease_token, allowed_statuses={'running'})
    if task.task_type != 'alpha_method_design':
        raise HTTPException(403, 'Evidence investigation requires a method task.')
    require_current_method_authority(db, task)
    contract = MethodTaskContract.model_validate(task.input_contract)
    if contract.retrieval_scope is None or 'search_evidence' not in contract.policy.investigation_tools:
        raise HTTPException(403, 'Task has no approved evidence search scope.')
    request_digest = digest_document({'query': query, 'scope': contract.retrieval_scope.model_dump(mode='json')})
    events = list(db.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id,
        TaskEvent.event_type.in_(['recovery_search_reserved', 'recovery_search_completed']))
        .order_by(TaskEvent.id)).all())
    matching = [event for event in events if event.payload['operation_id'] == operation_id]
    if matching:
        if any(event.payload['request_digest'] != request_digest for event in matching):
            raise HTTPException(409, 'Evidence operation identity conflict.')
        completed = next((event for event in matching if event.event_type == 'recovery_search_completed'), None)
        if completed is None:
            raise HTTPException(409, 'Evidence operation was reserved; do not repeat an uncertain query.')
        return completed.payload['receipt']
    if sum(event.event_type == 'recovery_search_reserved' for event in events) >= contract.policy.max_tool_calls:
        raise HTTPException(409, 'Evidence search budget exhausted.')
    binding = {'operation_id': operation_id, 'request_digest': request_digest}
    append_task_event(db, task, 'recovery_search_reserved', 'Bounded evidence search reserved.',
                      agent_id=agent.id, payload=binding)
    db.commit()  # Reserve before retrieval; interruptions never refund capacity.
    receipt = retrieve_scoped_evidence(db, scope=contract.retrieval_scope, query=query,
                                      task_id=task.id, operation_id=operation_id)
    # Recheck the lease and authority after retrieval, before disclosing evidence.
    db.refresh(task)
    verify_task_lease(task, agent, lease_token, allowed_statuses={'running'})
    require_current_method_authority(db, task)
    append_task_event(db, task, 'recovery_search_completed', 'Bounded evidence search retained.',
                      agent_id=agent.id, payload={**binding, 'receipt': receipt})
    db.commit()
    return receipt


def retrieve_scoped_evidence(db, *, scope, query, task_id, operation_id):
    request = HybridRetrievalRequest(query=query, project=scope.project,
                                    limit=scope.max_results)
    access = EvidenceAccessContext(actor='recovery-task:' + str(task_id),
        projects=frozenset({scope.project}), max_access_class=scope.max_access_class)
    result = hybrid_search(db, request, access)
    response = HybridRetrievalResponse.model_validate(result).model_dump(mode='json')
    if response['stale'] is not False:
        raise ValueError('Recovery retrieval requires a current projection')
    if len(response['hits']) > scope.max_results:
        raise ValueError('Recovery retrieval exceeded admitted result count')
    hits = []
    allowed_access = {'public'} if scope.max_access_class == 'public' else {'public', 'internal'}
    for hit in response['hits']:
        if (hit['project'] != scope.project or hit['access_class'] not in allowed_access
                or hit['citation']['object_id'] != hit['object_id']):
            raise ValueError('Recovery retrieval result violated scope or citation identity')
        original = hit['text']
        hits.append({**hit, 'text': original[:scope.max_excerpt_chars],
                     'excerpt_truncated': len(original) > scope.max_excerpt_chars,
                     'retrieved_text_digest': digest_document({'text': original})})
    return {'schema_version': 'recovery-evidence-search-v1', 'task_id': str(task_id),
        'operation_id': operation_id, 'scope': scope.model_dump(mode='json'),
        'request': request.model_dump(mode='json'), 'corpus_digest': response['corpus_digest'],
        'projection_version': response['projection_version'], 'abstained': response['abstained'],
        'hits': hits, 'scientific_approval': False, 'execution_authority': False}
