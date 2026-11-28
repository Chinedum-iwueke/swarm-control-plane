import asyncio

import pytest

from swarm_worker.engineering_episode import EpisodeIntegrityError
from swarm_worker.recovery_tools import bind_recovery_search, search_evidence


@pytest.mark.asyncio
async def test_recovery_search_is_task_local_and_resets_after_error():
    ready = asyncio.Event()
    entered = 0

    async def run(identity):
        nonlocal entered

        async def callback(query, operation):
            return identity, query, operation

        with pytest.raises(RuntimeError, match='execution interrupted'):
            with bind_recovery_search(callback):
                entered += 1
                if entered == 2:
                    ready.set()
                await ready.wait()
                assert await search_evidence('query', 'a' * 64) == (identity, 'query', 'a' * 64)
                raise RuntimeError('execution interrupted')
        with pytest.raises(EpisodeIntegrityError, match='No leased'):
            await search_evidence('query', 'b' * 64)

    await asyncio.gather(run('first-task'), run('second-task'))
    with pytest.raises(EpisodeIntegrityError, match='No leased'):
        await search_evidence('query', 'c' * 64)
