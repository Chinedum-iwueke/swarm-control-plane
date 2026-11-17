"""Explicit task-bound Codex session continuation; never resume the latest session."""
import json
import os
from uuid import UUID

from swarm_worker.engineering_episode import EpisodeIntegrityError
from swarm_worker.model_lane import model_call_allowed, provider_key


async def session_author(executor, *, state, binding, prompt, workspace, heartbeat,
                         heartbeat_failures, remaining):
    from swarm_worker.method_episode import MethodCapacityUnavailable
    if not await model_call_allowed():
        state['session_capacity_before_launch']=True
        raise MethodCapacityUnavailable('author provider circuit unavailable')
    environment=executor._codex_environment()
    lane=provider_key()
    home=(os.environ.get('SWARM_OPENAI_API_CODEX_HOME') if lane=='openai-api' else environment.get('CODEX_HOME'))
    if not home:
        raise EpisodeIntegrityError('author billing lane lacks a configured home')
    identity=dict(source=binding['source_commit'],contract=binding['contract_digest'],
        workspace=str(workspace.repository),model=executor._codex_model,
        home=home,provider=lane)
    retained=state.get('author_session')
    if retained and retained['binding']!=identity:
        raise EpisodeIntegrityError('session source/model/workspace/billing binding changed')
    if not retained and state['model_calls']>1 and not state.pop('session_capacity_before_launch',False):
        raise EpisodeIntegrityError('interrupted session identity unavailable; explicit successor required')
    # AsyncProcessRunner owns billing routing; do not route the same call twice.
    args=['codex','exec','--sandbox','workspace-write']
    if retained:
        session=str(UUID(retained['session_id']))
        args+=['resume',session]
    args+=['--ignore-user-config','--json','-c','sandbox_workspace_write.network_access=false',
           '--model',executor._codex_model,'--output-last-message',str(workspace.artifacts/'coder-summary.md'),'-']
    step=await executor._run_codex(name='coding-agent',args=args,
        prompt=prompt,workspace=workspace,heartbeat=heartbeat,heartbeat_failures=heartbeat_failures,
        timeout_seconds=remaining,environment_overrides=environment)
    sessions=set()
    with (workspace.logs/'coding-agent.stdout.log').open() as stream:
        for line in stream:
            if len(line)>1000000:
                raise EpisodeIntegrityError('oversized session event')
            try:
                event=json.loads(line)
            except ValueError:
                continue
            if isinstance(event,dict) and event.get('type')=='thread.started':
                sessions.add(str(UUID(event['thread_id'])))
    if len(sessions)>1 or (retained and sessions and sessions!={retained['session_id']}):
        raise EpisodeIntegrityError('Codex returned a different author session')
    if not retained and len(sessions)==1:
        state['author_session']={'binding':identity,'session_id':sessions.pop()}
    if step.success and not state.get('author_session'):
        raise EpisodeIntegrityError('successful author lacks durable session identity')
    return step
