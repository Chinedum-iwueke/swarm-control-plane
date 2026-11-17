import json

import pytest

from swarm_worker.engineering_episode import canonical_digest, EpisodeIntegrityError
from swarm_worker.executors.method_review import review_callbacks
from test_engineering_episode_executor import fixture, step
from test_method_review import identity, packet, verdict


async def heartbeat(_): pass


@pytest.mark.asyncio
async def test_exact_runtime_schema_and_ephemeral_review_context(tmp_path, monkeypatch):
    executor,_,_,workspace=fixture(tmp_path,'1',1)
    monkeypatch.delenv('SWARM_AGENT_TOKEN',raising=False)
    monkeypatch.setenv('SWARM_OPENAI_BILLING_LANE','subscription')
    who=identity('reviewer')
    context={'packet':packet(),'packet_digest':canonical_digest(packet())}
    calls=[]
    async def model(**kw):
        calls.append(kw)
        assert '--ephemeral' in kw['args'] and 'read-only' in kw['args']
        (kw['workspace'].artifacts/'verdict.json').write_text(json.dumps(verdict(context)))
        return step('method-review',kw['workspace'])
    executor._run_codex=model
    review,judge=review_callbacks({canonical_digest(who):executor},workspace,heartbeat)
    result=await review('strategy_spec',who,context,'a'*64,30)
    assert result['verdict']=='accept' and len(calls)==1
    with pytest.raises(EpisodeIntegrityError,match='not registered'):
        await judge(identity('unregistered'),context,'b'*64,30)
