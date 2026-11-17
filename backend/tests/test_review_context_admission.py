from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import alpha_campaign


@pytest.mark.parametrize('repeated', [True, False])
def test_review_context_admitted_before_task_publication(monkeypatch, repeated):
    db = MagicMock()
    assignment = SimpleNamespace(id=uuid4(), evaluator_profile_id=uuid4(), review_kind='strategy_spec')
    db.scalars.return_value.all.return_value = [assignment]
    db.scalar.return_value = None
    db.get.return_value = SimpleNamespace(machine='vm1-developer', agent_id=uuid4(),
        profile_digest='a'*64, package_digest='b'*64)
    route = SimpleNamespace(id=uuid4(), status='assigned', subject_digest='c'*64)
    subject = {'source_commit': 'd'*40, 'review_scope': 'method_design'}
    evidence = {'text': 'evidence' * 6000}
    qualification = {'card': evidence, 'artifact_bundle': {'packet': evidence}} if repeated else {
        'card': {}, 'artifact_bundle': {'text': 'x' * 101000}}
    saved = MagicMock()
    monkeypatch.setattr(alpha_campaign, 'persist_new_task', saved)
    if repeated:
        alpha_campaign._materialize_strategy_review_tasks(db, route, subject, qualification)
        saved.assert_called_once()
    else:
        with pytest.raises(HTTPException, match='after lossless'):
            alpha_campaign._materialize_strategy_review_tasks(db, route, subject, qualification)
        saved.assert_not_called()
