"""Opt-in actual Bulletproof CLI; synthetic contracts and scripted reasoning only."""
import os
from pathlib import Path
import subprocess

import pytest

from swarm_worker.engineering_episode import canonical_digest
from swarm_worker.method_episode import MethodEpisode, MethodEpisodePolicy
from swarm_worker.native_diagnostic_client import NativeDiagnosticClient


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['meaningful_effect', 'dependence_assumptions', 'calibration'])
async def test_actual_native_contract_repair_and_custody(tmp_path, missing):
    location = os.environ.get('BULLETPROOF_DIAGNOSTIC_REPO')
    if not location:
        pytest.skip('requires explicit clean Bulletproof checkout with AEP-003')
    root = Path(location)
    source = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip()
    client = NativeDiagnosticClient(root, root/'.venv/bin/python', source)
    evidence = {'kind':'synthetic_test_assumption', 'not_market_evidence':True}
    catalog = {canonical_digest(evidence):evidence}
    design = dict(schema_version='design-adequacy-contract-v1', estimand='synthetic residual contrast',
        estimator_id='proposed', meaningful_effect=dict(value=.25, units='residual SD',
            justification='Fixture only', evidence_digests=list(catalog)),
        dependence_assumptions='AR sensitivity required', multiplicity='single primary',
        eligibility_policy='frozen support', undefined_replicate_policy='invalidate',
        calibration=dict(seed=42, outer_replicates=100, inner_replicates=199,
            max_work_units=100000, dgp_ids=['null_iid']))
    initial = {key:value for key,value in design.items() if key!=missing}
    async def diagnose(proposal, operation, work, remaining):
        if missing not in proposal['method']:
            check = {'kind':'deterministic_contract_preflight', 'missing':missing,
                'proposal_digest':canonical_digest(proposal)}
            digest = canonical_digest(check)
            return dict(disposition='repair', work_units=1, evidence={digest:check},
                findings=[dict(requirement_ref=missing, evidence_digest=digest,
                    message='Required design contract field missing', verification='Native design contract validation')])
        receipt = await client.run(tool='design_adequacy_v1', subject_digest=canonical_digest(proposal),
            payload=proposal['method'], catalog=catalog, work_limit=work, timeout=remaining)
        assert receipt['result']['status'] == 'requires_independent_review_and_native_calibration'
        assert receipt['execution_authority'] is False
        return dict(disposition='ready', findings=[], work_units=1,
                    evidence={canonical_digest(receipt):receipt})
    async def scripted_model(context, *_):
        return dict(changes={missing:design[missing]}, addressed_findings=context['finding_digests'],
                    rationale='Restore explicit obligation; not scientific validation')
    episode = MethodEpisode(tmp_path/'episode', binding=dict(task_id='offline-pilot',source_commit=source,
        mandate_digest='a'*64, findings_digest='b'*64),
        proposal=dict(scientific_identity={'target':'synthetic residual contrast'},
            support_minima={'rows':100}, method=initial),
        policy=MethodEpisodePolicy(allowed_method_fields=[missing]),
        diagnose=diagnose, propose=scripted_model, authorized=lambda _: True)
    state = await episode.run()
    assert state['status'] == 'ready_for_independent_review'
    assert state['repairs'] == 1 and state['tool_calls'] == 2
    assert any(doc.get('schema_version') == 'native-diagnostic-receipt-v1' for doc in state['evidence'].values())
    assert await episode.run() == state
