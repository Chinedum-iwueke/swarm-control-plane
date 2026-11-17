"""Fixed-command AEP-003 transport for trusted method-episode tool adapters."""
import asyncio
import json
import os
from pathlib import Path
import signal

from swarm_worker.engineering_episode import EpisodeIntegrityError, canonical_digest
from swarm_worker.method_episode import bounded


TOOLS = frozenset({'design_adequacy_v1', 'event_support_v1',
                   'requirements_feasibility_v1', 'residual_calibration_v1'})


class NativeDiagnosticClient:
    def __init__(self, repository: Path, python: Path, source_commit: str):
        self.repository, self.python, self.source = repository.resolve(), python.absolute(), source_commit

    async def run(self, *, tool, subject_digest, payload, catalog, work_limit, timeout):
        if tool not in TOOLS:
            raise EpisodeIntegrityError('unregistered native diagnostic tool')
        if type(work_limit) is not int or not 1 <= work_limit <= 10000000 or not 0 < timeout <= 7200:
            raise EpisodeIntegrityError('invalid diagnostic execution bound')
        if tool == 'residual_calibration_v1':
            declared = payload.get('design', {}).get('calibration', {}).get('max_work_units')
            if type(declared) is not int or declared > work_limit:
                raise EpisodeIntegrityError('calibration exceeds episode reservation')
        request = dict(schema_version='native-diagnostic-request-v1', tool=tool,
            source_commit=self.source, subject_digest=subject_digest, payload=payload)
        envelope = bounded(dict(request=request, evidence_catalog=catalog))
        # No shell, model-provided command, network tool or inherited auth variables.
        process = await asyncio.create_subprocess_exec(str(self.python),
            str(self.repository/'scripts/run_native_diagnostic.py'), cwd=self.repository,
            env={'PATH': '/usr/bin:/bin', 'PYTHONPATH':str(self.repository/'src'),
                 'PYTHONDONTWRITEBYTECODE':'1', 'LANG':'C.UTF-8'},
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True)

        async def read(stream):
            chunks, size = [], 0
            while chunk := await stream.read(8192):
                size += len(chunk)
                if size > 262144:
                    raise EpisodeIntegrityError('diagnostic output exceeds bound')
                chunks.append(chunk)
            return b''.join(chunks)

        async def exchange():
            process.stdin.write(json.dumps(envelope, allow_nan=False).encode())
            await process.stdin.drain()
            process.stdin.close()
            stdout, stderr = await asyncio.gather(read(process.stdout), read(process.stderr))
            await process.wait()
            return stdout, stderr

        task = asyncio.create_task(exchange())
        try:
            stdout, stderr = await asyncio.wait_for(task, timeout)
            if process.returncode:
                # Do not reinterpret an infrastructure traceback as scientific evidence.
                raise EpisodeIntegrityError(f'native diagnostic exited {process.returncode}; '
                    f'stderr digest={canonical_digest(stderr.decode(errors="replace"))}')
            receipt = json.loads(stdout)
            if (receipt.get('schema_version') != 'native-diagnostic-receipt-v1'
                    or receipt.get('receipt_digest') != canonical_digest({k:v for k,v in receipt.items() if k!='receipt_digest'})
                    or receipt.get('request_digest') != canonical_digest(request)
                    or receipt.get('evidence_catalog_digest') != canonical_digest(catalog)
                    or receipt.get('source_commit') != self.source
                    or receipt.get('subject_digest') != subject_digest
                    or receipt.get('tool') != tool
                    or any(receipt.get(key) is not False for key in
                           ('execution_authority','scientific_certification','market_data_used'))):
                raise EpisodeIntegrityError('native diagnostic custody mismatch')
            return receipt
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
