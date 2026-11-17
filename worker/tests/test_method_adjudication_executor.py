import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from test_alpha_strategy_review_executor import contract
from swarm_worker.executors.alpha_strategy_review import AlphaStrategyReviewExecutor
from swarm_worker.strategy_review_contract import review_digest as digest


@pytest.mark.asyncio
async def test_independent_adjudicator_emits_recheck_not_approval(tmp_path, monkeypatch):
    monkeypatch.delenv('SWARM_AGENT_TOKEN', raising=False)
    raw = contract()
    evidence = {'kind': 'synthetic scope evidence'}
    packet = {'requirements': {'target': 'exact'}, 'evidence': {digest(evidence): evidence}}
    finding = {'criterion': 'target', 'evidence_digests': [digest(evidence)],
               'violation': 'Scope disputed', 'verification': 'Inspect exact obligation'}
    reviews = [{'method_verdict': {'findings': [finding]}}]
    bundle = {'method_review_packet': packet, 'rejected_reviews': reviews}
    raw['review_kind'] = 'method_adjudication'
    raw['qualification']['artifact_bundle'] = bundle
    raw['subject'].update(review_scope='method_adjudication', artifact_bundle_digest=digest(bundle))
    raw['subject_digest'] = digest(raw['subject'])
    for name in ('artifacts', 'logs', 'repository'):
        (tmp_path/name).mkdir()
    workspace = SimpleNamespace(artifacts=tmp_path/'artifacts', logs=tmp_path/'logs',
        repository=tmp_path/'repository', plan=SimpleNamespace(resolved_base_commit=raw['base_ref']))
    calls = []
    class Runner:
        async def start(self, args, **kwargs):
            calls.append(args)
            assert '--ephemeral' in args and 'read-only' in args
            prompt = kwargs['stdin'].read().decode()
            assert 'Outer verdict MUST remain reject' in prompt
            assert 'Inspect the pinned native implementation' not in prompt
            output = dict(subject_digest=raw['subject_digest'], verdict='reject',
                rationale='Independent interpretation recheck, not scientific approval.', checks=['target'],
                blockers=['Fresh independent review required'], method_adjudication={
                    'packet_digest': digest(packet), 'reviews_digest': digest(reviews), 'decision': 'recheck',
                    'finding_evidence': {digest(finding): [digest(evidence)]},
                    'rationale': 'The exact pre-authoring scope warrants fresh independent review.'})
            (workspace.artifacts/'strategy-review.json').write_text(json.dumps(output))
            return SimpleNamespace(process=SimpleNamespace(returncode=0))
    executor = AlphaStrategyReviewExecutor(codex_home=tmp_path, codex_model='fixture',
        heartbeat_interval_seconds=1, process_runner=Runner(), effective_uid=lambda:1000)
    async def heartbeat(_): pass
    result = await executor.execute(task=SimpleNamespace(input_contract=raw,
        assigned_agent_id=UUID(raw['evaluator_agent_id']), attempt_count=1),
        workflow=SimpleNamespace(name=raw['workflow'], steps=[], timeout_seconds=60),
        workspace=workspace, heartbeat=heartbeat)
    assert result.success and len(calls) == 1
    assert result.summary['alpha_strategy_review']['verdict'] == 'reject'
    assert result.summary['alpha_strategy_review']['method_adjudication']['decision'] == 'recheck'
