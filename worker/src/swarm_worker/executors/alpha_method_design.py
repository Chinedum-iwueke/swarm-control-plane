"""Registered-task adapter for the bounded method episode and native diagnosis."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import time

from swarm_worker.engineering_episode import canonical_digest as digest
from swarm_worker.executors.code_validation import RootExecutionError
from swarm_worker.executors.method_episode import correction_proposer
from swarm_worker.method_episode import MethodEpisode
from swarm_worker.method_review import method_review_packet
from swarm_worker.method_task import MethodTaskContract
from swarm_worker.model_lane import model_capacity_permit, provider_key
from swarm_worker.models import WorkflowExecutionResult
from swarm_worker.native_diagnostic_client import NativeDiagnosticClient
from swarm_worker.native_design_shape import defects, SHAPE


def compact_method_result(document):
    """Transport catalog envelopes by hash; keep the durable episode unchanged."""
    result = deepcopy(document)
    state = result['state']
    evidence = state['evidence']
    envelopes = {key: value for key, value in evidence.items()
        if set(value) == {'disposition', 'evidence', 'findings', 'work_units'}
        and isinstance(value['evidence'], dict)
        and all(evidence.get(ref) == doc for ref, doc in value['evidence'].items())}
    # Only flatten envelopes whose children are leaf documents, never cycles.
    envelopes = {key: value for key, value in envelopes.items()
                 if not set(value['evidence']) & set(envelopes)}
    if envelopes:
        result['schema_version'] = 'method-task-result-v2'
        result['audit_state_digest'] = digest(state)
        result['state_evidence_envelopes'] = {
            key: value | {'evidence': sorted(value['evidence'])}
            for key, value in envelopes.items()}
        state['evidence'] = {key: value for key, value in evidence.items() if key not in envelopes}
    return result


class AlphaMethodDesignExecutor:
    def __init__(self, engineering, *, python, effective_uid=os.geteuid):
        self.engineering, self.python, self.uid = engineering, python, effective_uid

    async def execute(self, *, task, workflow, workspace, heartbeat):
        if self.uid() == 0:
            raise RootExecutionError('Method design must not run as root')
        if self.python is None:
            raise ValueError('Method design requires the configured native validation environment')
        contract = MethodTaskContract.model_validate(task.input_contract)
        if (workflow.name != contract.workflow or workflow.steps
                or workflow.task_type != 'alpha_method_design'
                or workspace.metadata.resolved_base_commit != contract.base_ref):
            raise ValueError('Method workflow/source binding mismatch')
        started = time.monotonic()
        client = NativeDiagnosticClient(workspace.repository, self.python, contract.base_ref)
        binding = dict(task_id=str(task.id), source_commit=contract.base_ref,
            mandate_digest=contract.mandate_digest, findings_digest=contract.findings_digest,
            contract_digest=digest(contract.model_dump(mode='json')))
        root = workspace.plan.attempt_directory.parent / 'method-episode'

        async def check_lease(stage):
            await heartbeat({'phase': 'method_design', 'stage': stage,
                             'candidate_id': str(contract.candidate_id)})
            if datetime.now(timezone.utc) >= contract.valid_until:
                raise ValueError('Method authority expired')

        async def diagnose(proposal, operation, work, remaining):
            await check_lease('native_diagnosis')
            retained = contract.evidence_catalog.get(contract.findings_digest, {})
            if (retained.get('schema_version') == 'method-review-correction-v1'
                    and retained.get('proposal_digest') == digest(proposal)):
                findings = [dict(requirement_ref=finding['criterion'], evidence_digest=contract.findings_digest,
                                 message=finding['violation'], verification=finding['verification'])
                            for review in retained['reviews'] for finding in review['method_verdict']['findings']]
                if not findings:
                    raise ValueError('Review correction has no retained findings')
                return dict(disposition='repair', work_units=1, findings=findings,
                            evidence=contract.evidence_catalog)
            # Missing fields are cheap, attributable preflight findings. Invalid
            # native values fail closed, never become invented passing receipts.
            invalid = defects(proposal['method'])
            if 'meaningful_effect' not in invalid:
                if any(ref not in contract.evidence_catalog
                       for ref in proposal['method']['meaningful_effect']['evidence_digests']):
                    invalid['meaningful_effect'] = 'Justification must reference evidence in the retained contract catalog'
            if invalid:
                report = {'schema_version': 'method-fields-preflight-v1',
                          'proposal_digest': digest(proposal), 'defects': invalid,
                          'required_shape': SHAPE}
                key = digest(report)
                return dict(disposition='repair', work_units=1,
                    evidence={**contract.evidence_catalog, key: report},
                    findings=[dict(requirement_ref='native_design.' + field, evidence_digest=key,
                        message=message,
                        verification='Exact native design-adequacy field shape') for field, message in invalid.items()])
            receipt = await client.run(tool=contract.diagnostic, subject_digest=digest(proposal),
                payload=proposal['method'], catalog=contract.evidence_catalog,
                work_limit=work, timeout=remaining)
            if receipt['result'].get('status') == 'requires_method_correction':
                findings = receipt['result'].get('consistency', {}).get('findings', [])
                if not findings:
                    raise ValueError('Native correction requires concrete consistency findings')
                if any(f.get('disposition') != 'repair' for f in findings):
                    return dict(disposition='requires_new_question', work_units=1, findings=[],
                                evidence={**contract.evidence_catalog, digest(receipt): receipt})
                return dict(disposition='repair', work_units=1,
                    evidence={**contract.evidence_catalog, digest(receipt): receipt},
                    findings=[dict(requirement_ref='calibration_consistency.'+f['code'],
                        evidence_digest=digest(receipt), message=f['path']+': '+f['message'],
                        verification='Native experiment-to-calibration consistency check') for f in findings])
            if receipt['result'].get('status') != 'requires_independent_review_and_native_calibration':
                raise ValueError('Unexpected native design diagnostic status')
            if 'experiment' in proposal['method']:
                consistency = receipt['result'].get('consistency', {})
                if (consistency.get('status') != 'structurally_consistent'
                        or consistency.get('finding_count') != 0 or consistency.get('findings') != []):
                    raise ValueError('Structured method lacks native consistency readiness')
            return dict(disposition='ready', findings=[], work_units=1,
                evidence={**contract.evidence_catalog, digest(receipt): receipt})

        async def propose(context, operation, remaining):
            await check_lease('method_correction')
            return await adapter(context, operation, remaining)

        async def model_permitted():
            await check_lease('method_correction_permit')
            return (await model_capacity_permit()).get('allowed') is True

        episode = MethodEpisode(root, binding=binding, proposal=contract.proposal,
            policy=contract.policy, diagnose=diagnose, propose=propose,
            authorized=lambda _: datetime.now(timezone.utc) < contract.valid_until,
            model_permitted=model_permitted)
        adapter = correction_proposer(self.engineering, workspace, heartbeat,
            read_evidence=episode.read_evidence, max_context_bytes=contract.policy.max_context_bytes,
            context_evidence=contract.evidence_catalog)
        permit = await model_capacity_permit()
        async def run_with_lease():
            pending = asyncio.create_task(episode.run(recovery_token=(permit.get('recovery_token')
                                  if permit.get('allowed') is True else None)))
            try:
                while not pending.done():
                    try:
                        return await asyncio.wait_for(asyncio.shield(pending), timeout=20)
                    except TimeoutError:
                        await check_lease('method_episode')
                return await pending
            finally:
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

        # Revalidate the lease even when a completed checkpoint is reused.
        await heartbeat({'phase': 'method_design', 'stage': 'authorization'})
        state = await asyncio.wait_for(run_with_lease(), timeout=min(
            workflow.timeout_seconds, contract.policy.max_duration_seconds))
        document = {'schema_version': 'method-task-result-v1',
                    'contract_digest': binding['contract_digest'], 'state': state,
                    'scientific_approval': False, 'execution_authority': False}
        if state['status'] == 'ready_for_independent_review':
            # Diagnostic return envelopes duplicate the catalog. Retain them in
            # the audit state, but give reviewers each underlying document once.
            evidence = {k: v for k, v in state['evidence'].items()
                if not (set(v) == {'disposition', 'evidence', 'findings', 'work_units'}
                    and isinstance(v['evidence'], dict)
                    and all(state['evidence'].get(ref) == doc
                            for ref, doc in v['evidence'].items()))}
            document['review_packet'] = method_review_packet(state,
                requirements=contract.requirements, evidence=evidence,
                dependencies=contract.dependencies)
        document = compact_method_result(document)
        document['result_digest'] = digest(document)
        path = workspace.artifacts / 'method-episode-result.json'
        path.write_text(json.dumps(document, sort_keys=True))
        path.chmod(0o600)
        capacity = state['status'] == 'deferred' and state.get('reason') == 'capacity'
        summary = {'method_episode': document}
        if capacity:
            summary['provider_capacity'] = {'provider': provider_key(),
                'failure_summary': 'Method episode awaits provider recovery', 'retry_after_seconds': 21600}
        await heartbeat({'phase': 'method_design', 'stage': state['stage'],
            'status': state['status'], 'blocker': state.get('reason'),
            'repairs': state['repairs'], 'model_calls': state['model_calls'],
            'max_model_calls': contract.policy.max_model_calls, 'usage_known': False})
        return WorkflowExecutionResult(workflow=workflow.name, repository=contract.repository,
            base_commit=contract.base_ref, task_attempt=task.attempt_count,
            total_duration_seconds=time.monotonic()-started, steps=[],
            success=not capacity, termination_reason='provider_capacity' if capacity else None,
            retryable=False, summary=summary, artifacts=['artifacts/method-episode-result.json'])
