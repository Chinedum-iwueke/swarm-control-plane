from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.evaluator_routing import digest, historical_profile_producer_identity


def fixture():
    now = datetime.now(timezone.utc)
    actor, package = uuid4(), uuid4()
    document = dict(agent_id=str(actor), package_id=str(package), profile_version='1.0.0',
        review_kinds=['strategy_spec'], capabilities=['research-audit'], provider='native',
        model_family='deterministic', context_group='isolated-producer', registered_by='operator',
        machine='vm1', runtime='hermes/1', package_digest='a'*64)
    profile = SimpleNamespace(**{**document, 'agent_id':actor, 'package_id':package},
        id=uuid4(), profile_digest=digest(document), created_at=now-timedelta(days=2), retired_at=now+timedelta(days=1))
    event = SimpleNamespace(id=42, agent_id=actor, created_at=now,
        payload={'effective_authority':[{'package_digest':'a'*64}]})
    task = SimpleNamespace(id=uuid4(), attempt_count=2, input_contract={'stage':'prepare_execution'})
    db = MagicMock();db.scalar.return_value=event;db.scalars.return_value.all.return_value=[profile]
    return db,task,event,profile


def test_historical_profile_resolution_retains_proof_without_mutating_history():
    db,task,event,profile=fixture()
    identity,proof=historical_profile_producer_identity(db,task)
    assert identity['profile_digest']==profile.profile_digest
    assert proof['lease_payload_digest']==digest(event.payload)
    assert proof['lease_event_id']==42 and proof['task_attempt']==2
    assert proof['identity_digest']==digest(identity)
    db.add.assert_not_called()
    assert 'producer_identity' not in event.payload


@pytest.mark.parametrize('failure', ['future','retired','ambiguous','tampered','snapshot','digest_only','package','actor'])
def test_historical_resolution_fails_closed(failure):
    db,task,event,profile=fixture()
    if failure=='future': profile.created_at=event.created_at+timedelta(seconds=1)
    elif failure=='retired': profile.retired_at=event.created_at
    elif failure=='ambiguous': db.scalars.return_value.all.return_value=[profile,profile]
    elif failure=='tampered': profile.model_family='changed'
    elif failure=='snapshot': event.payload['producer_identity']={}
    elif failure=='digest_only': event.payload['producer_identity_digest']='b'*64
    elif failure=='package': profile.package_digest='c'*64
    else: profile.agent_id=uuid4()
    assert historical_profile_producer_identity(db,task) is None
