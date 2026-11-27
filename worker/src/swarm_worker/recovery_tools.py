"""Bounded inspection of immutable source; no model-selected shell commands."""
import asyncio
import re
from pathlib import PurePosixPath

from swarm_worker.engineering_episode import EpisodeIntegrityError


async def read_pinned_source(repository, source_commit, path, *, timeout):
    if (not re.fullmatch(r'[a-f0-9]{40}', source_commit)
            or not isinstance(path, str)
            or not re.fullmatch(r'(src/bt|scripts|tests)/[A-Za-z0-9_./-]+\.py', path)
            or '..' in PurePosixPath(path).parts):
        raise EpisodeIntegrityError('source inspection is restricted to pinned native Python files')
    process = await asyncio.create_subprocess_exec(
        '/usr/bin/git', '--no-replace-objects', '--no-pager', 'show', f'{source_commit}:{path}',
        cwd=repository, env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1',
                             'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        async def read():
            try:
                content = await process.stdout.readexactly(65537)
            except asyncio.IncompleteReadError as error:
                content = error.partial
            if len(content) > 65536:
                return {'status': 'unavailable', 'reason': 'file_exceeds_inspection_bound'}
            if await process.wait() != 0:
                return {'status': 'unavailable', 'reason': 'pinned_file_could_not_be_read'}
            try:
                return {'status': 'available', 'content': content.decode('utf-8')}
            except UnicodeDecodeError:
                return {'status': 'unavailable', 'reason': 'file_is_not_utf8'}
        result = await asyncio.wait_for(read(), timeout=timeout)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    return {'schema_version': 'recovery-source-inspection-v1', 'source_commit': source_commit,
            'path': path, **result, 'execution_authority': False}
