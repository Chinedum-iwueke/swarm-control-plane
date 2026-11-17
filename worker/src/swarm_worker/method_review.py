"""Evidence-bound method review. Adjudication can request re-review, never approve."""
import asyncio
from copy import deepcopy
import re
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swarm_worker.engineering_episode import EpisodeStore, EpisodeIntegrityError, canonical_digest
from swarm_worker.method_episode import bounded, MethodCapacityUnavailable


class ReviewIdentity(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    agent_id: str = Field(min_length=1, max_length=200)
    profile_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    context_group: str = Field(min_length=1, max_length=200)


class ReviewPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    max_model_calls: int = Field(default=5, ge=2, le=10)
    max_tool_calls: int = Field(default=1, ge=0, le=2)
    max_rechecks: int = Field(default=1, ge=0, le=1)
    tool_work_limit: int = Field(default=250000, ge=1, le=1000000)
    duration_seconds: int = Field(default=1800, ge=1, le=7200)
    context_bytes: int = Field(default=80000, ge=1024, le=128000)


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    criterion: str = Field(min_length=1, max_length=200)
    evidence_digests: list[str] = Field(min_length=1, max_length=16)
    violation: str = Field(min_length=1, max_length=4000)
    verification: str = Field(min_length=1, max_length=2000)


class MethodVerdict(BaseModel):
    model_config = ConfigDict(extra='forbid')
    packet_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    verdict: Literal['accept', 'reject']
    checks: list[str] = Field(min_length=1, max_length=64)
    findings: list[ReviewFinding] = Field(max_length=32)
    rationale: str = Field(min_length=1, max_length=4000)

    @model_validator(mode='after')
    def consistent(self):
        if (self.verdict == 'accept') == bool(self.findings):
            raise ValueError('acceptance must have no findings; rejection needs findings')
        return self


class Adjudication(BaseModel):
    model_config = ConfigDict(extra='forbid')
    packet_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['recheck', 'disputed']
    counterevidence_digests: list[str] = Field(max_length=32)
    rationale: str = Field(min_length=1, max_length=4000)


def method_review_packet(method_state, *, requirements, evidence, dependencies, prior_requirements=None):
    """Bridge a verified AEP-004 state to review without altering its proposal."""
    if (method_state.get('status') != 'ready_for_independent_review'
            or method_state.get('scientific_approval') is not False
            or method_state.get('execution_authority') is not False):
        raise EpisodeIntegrityError('method episode is not ready for independent review')
    retained = method_state.get('evidence', {})
    if not evidence or any(retained.get(key) != value for key, value in evidence.items()):
        raise EpisodeIntegrityError('review evidence is not retained by method episode')
    return bounded(dict(schema_version='method-review-packet-v1',
        method_episode_digest=canonical_digest(method_state),
        source_commit=method_state['binding']['source_commit'],
        proposal=deepcopy(method_state['proposal']), requirements=deepcopy(requirements),
        evidence=deepcopy(evidence), dependencies=deepcopy(dependencies),
        prior_requirements=deepcopy(prior_requirements or {})))


class MethodReviewEpisode:
    """Fixed independently routed reviewers, trusted tools, separate adjudicator.

    `current` must verify authority, dependency validity AND evaluator registration
    on every invocation, including cached results. `verify_counterevidence` verifies
    tool-execution custody outside model output. Callbacks are application code,
    never model-supplied plugins. Production routing remains with existing AGT-006.
    """
    def __init__(self, root, *, packet, producers, reviewers, adjudicator,
                 policy, review, counterexamples, adjudicate, current,
                 verify_counterevidence):
        bounded(packet, policy.context_bytes)
        if (set(packet) != {'schema_version','method_episode_digest','source_commit','proposal',
                           'requirements','evidence','dependencies','prior_requirements'}
                or packet['schema_version'] != 'method-review-packet-v1'
                or not isinstance(packet['requirements'], dict) or not packet['requirements']
                or len(packet['requirements']) > 64):
            raise ValueError('invalid exact review packet')
        if not isinstance(packet['evidence'], dict) or not packet['evidence'] or any(
                canonical_digest(doc) != digest for digest, doc in packet['evidence'].items()):
            raise ValueError('review evidence digest mismatch')
        for field, length in (('source_commit',40), ('method_episode_digest',64)):
            if not isinstance(packet[field], str) or not re.fullmatch(f'[a-f0-9]{{{length}}}', packet[field]):
                raise ValueError('invalid review source binding')
        if (not isinstance(packet['prior_requirements'], dict)
                or not isinstance(packet['dependencies'], dict) or not packet['dependencies']
                or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v)
                       for v in packet['dependencies'].values())
                or any(not isinstance(k,str) or not 1<=len(k)<=200
                       for k in [*packet['requirements'],*packet['prior_requirements']])):
            raise ValueError('explicit requirements and dependency digests required')
        if set(reviewers) != {'strategy_spec','causality_leakage'} or not producers:
            raise ValueError('both independent review kinds and producer identities required')
        identities = [ReviewIdentity.model_validate(i) for i in producers]
        evaluated = {k:ReviewIdentity.model_validate(v) for k,v in reviewers.items()}
        judge = ReviewIdentity.model_validate(adjudicator)
        actors = [*evaluated.values(), judge]
        if (len({i.agent_id for i in actors}) != 3 or len({i.context_group for i in actors}) != 3
                or any(a.agent_id == p.agent_id or a.context_group == p.context_group
                       for a in actors for p in identities)):
            raise ValueError('producer, reviewers and adjudicator require distinct agents and contexts')
        self.packet, self.policy = deepcopy(packet), policy
        self.identities = {k:v.model_dump() for k,v in evaluated.items()}
        self.judge = judge.model_dump()
        binding = dict(kind='method-review-episode-v1', packet_digest=canonical_digest(packet),
            producers=[p.model_dump() for p in identities], reviewers=self.identities,
            adjudicator=self.judge, policy=policy.model_dump())
        self.store = EpisodeStore(root, binding, policy.duration_seconds, str(root))
        self.review, self.counterexamples, self.adjudicate = review, counterexamples, adjudicate
        self.current, self.verify_counterevidence = current, verify_counterevidence

    async def run(self, *, recovery_token=None):
        with self.store.locked():
            state = self.store.load()
            if 'packet' not in state:
                state.update(packet=deepcopy(self.packet), stage='review', reviews={}, history=[],
                    tool_calls=0, reserved_work=0, rechecks=0, recovery_token=recovery_token,
                    scientific_approval=False, execution_authority=False)
            # Never return a cached acceptance whose dependencies/profile are invalid now.
            if self.current(deepcopy(self.store.binding)) is not True:
                return {**state, 'status':'deferred', 'reason':'review_dependencies_or_authority_invalid'}
            if state['status'] in {'review_complete','rejected','disputed','blocked'}:
                return state
            if state['status'] == 'deferred':
                if state.get('reason') not in {'capacity','authority_changed'} or not recovery_token or recovery_token == state['recovery_token']:
                    return state
                state['recovery_token'] = recovery_token
            state['status'] = 'running'
            if state['pending'] is not None:
                state['history'].append({'interrupted':state['pending']})
                state['pending'] = None
            while state['status'] == 'running':
                remaining = state['deadline']-time.time()
                if remaining <= 0:
                    state.update(status='deferred', reason='deadline_exhausted')
                    break
                if self.current(deepcopy(self.store.binding)) is not True:
                    state.update(status='deferred', reason='authority_changed')
                    break
                packet_digest = canonical_digest(state['packet'])
                stage = state['stage']
                kind = next((k for k in sorted(self.identities) if k not in state['reviews']), None)
                if stage == 'review' and kind is None:
                    rejected = [v for v in state['reviews'].values() if v['verdict']['verdict']=='reject']
                    if not rejected:
                        state.update(status='review_complete', reason='both_independent_reviews_accept')
                        break
                    if state['rechecks'] >= self.policy.max_rechecks:
                        state.update(status='rejected', reason='fresh_review_rejected')
                        break
                    state['stage'] = 'counterexamples'
                    continue
                try:
                    requirements, prior = state['packet']['requirements'], state['packet']['prior_requirements']
                    context = bounded({'packet':state['packet'], 'packet_digest':packet_digest,
                        'changed_criteria':sorted(k for k in set(requirements)|set(prior)
                                                  if requirements.get(k)!=prior.get(k)),
                        'reviews':state['reviews'], 'counterevidence':state.get('counterevidence',{})}, self.policy.context_bytes)
                except EpisodeIntegrityError:
                    state.update(status='deferred', reason='context_requires_compaction')
                    break
                if stage == 'counterexamples':
                    if state['tool_calls'] >= self.policy.max_tool_calls:
                        state.update(status='disputed', reason='counterexample_budget_exhausted')
                        break
                    state['tool_calls'] += 1
                    state['reserved_work'] += self.policy.tool_work_limit
                else:
                    if state['model_calls'] >= self.policy.max_model_calls:
                        state.update(status='deferred', reason='model_budget_exhausted')
                        break
                    state['model_calls'] += 1
                operation = canonical_digest([self.store.binding, len(state['history']), stage, kind, packet_digest])
                state['pending'] = operation
                self.store.save(state)
                raw = None
                try:
                    if stage == 'review':
                        reviewer_context = deepcopy(context)
                        reviewer_context.pop('reviews')  # No peer verdicts in independent review context.
                        raw = await asyncio.wait_for(self.review(kind, deepcopy(self.identities[kind]),
                            reviewer_context, operation, remaining), remaining)
                        verdict = MethodVerdict.model_validate(bounded(raw)).model_dump()
                        if (verdict['packet_digest'] != packet_digest
                                or len(verdict['checks']) != len(set(verdict['checks']))
                                or set(verdict['checks']) != set(state['packet']['requirements'])):
                            raise ValueError('review omitted criteria or changed packet')
                        for finding in verdict['findings']:
                            if (finding['criterion'] not in state['packet']['requirements']
                                    or not set(finding['evidence_digests']) <= set(state['packet']['evidence'])):
                                raise ValueError('finding lacks concrete criterion or evidence')
                        state['reviews'][kind] = {'identity':self.identities[kind], 'verdict':verdict}
                        result = state['reviews'][kind]
                    elif stage == 'counterexamples':
                        raw = await asyncio.wait_for(self.counterexamples(deepcopy(context),
                            operation, self.policy.tool_work_limit, remaining), remaining)
                        result = bounded(raw)
                        findings = {canonical_digest(f):f for r in state['reviews'].values()
                                    for f in r['verdict']['findings']}
                        if not isinstance(result, dict) or not result or len(result)>32:
                            raise ValueError('bounded counterevidence required')
                        for digest, receipt in result.items():
                            if (canonical_digest(receipt) != digest
                                    or receipt.get('packet_digest') != packet_digest
                                    or receipt.get('finding_digest') not in findings
                                    or receipt.get('criterion') != findings[receipt['finding_digest']]['criterion']
                                    or receipt.get('outcome') not in {'supports','contradicts','inconclusive'}
                                    or receipt.get('execution_authority') is not False
                                    or self.verify_counterevidence(deepcopy(receipt), deepcopy(context), operation,
                                                                  self.policy.tool_work_limit) is not True):
                                raise ValueError('counterexample custody or relevance differs')
                        state['counterevidence'] = result
                        contradicted = {r['finding_digest'] for r in result.values() if r['outcome']=='contradicts'}
                        if contradicted != set(findings):
                            state.update(status='disputed', reason='counterevidence_does_not_cover_rejections')
                        else:
                            state['stage'] = 'adjudicate'
                    else:
                        raw = await asyncio.wait_for(self.adjudicate(deepcopy(self.judge), deepcopy(context), operation, remaining), remaining)
                        result = Adjudication.model_validate(bounded(raw)).model_dump()
                        if result['packet_digest'] != packet_digest:
                            raise ValueError('adjudication packet differs')
                        references = set(result['counterevidence_digests'])
                        available = state['counterevidence']
                        if not references <= set(available):
                            raise ValueError('adjudication cites unrecorded counterevidence')
                        needed = {canonical_digest(f) for r in state['reviews'].values() for f in r['verdict']['findings']}
                        if result['decision'] == 'recheck':
                            if (not references or not references <= set(available)
                                    or any(available[d]['outcome']!='contradicts' for d in references)
                                    or {available[d]['finding_digest'] for d in references} != needed):
                                raise ValueError('unrelated or incomplete counterevidence cannot dismiss rejection')
                            state['packet']['evidence'].update({d:available[d] for d in sorted(references)})
                            # Evidence changed: invalidate BOTH cached verdicts, retain history.
                            state['reviews'] = {}
                            state['rechecks'] += 1
                            state['stage'] = 'review'
                        else:
                            state.update(status='disputed', reason='adjudication_unresolved')
                    state['history'].append({'stage':stage, 'kind':kind, 'operation':operation,
                        'packet_digest':packet_digest, 'result':deepcopy(result)})
                except MethodCapacityUnavailable:
                    state.update(status='deferred', reason='capacity')
                    state['history'].append({'stage':stage,'operation':operation,'status':'capacity'})
                except TimeoutError:
                    state.update(status='deferred', reason='deadline_exhausted')
                except (ValueError, TypeError, EpisodeIntegrityError):
                    state.update(status='blocked', reason='invalid_review_or_adjudication_evidence')
                    try:
                        invalid = deepcopy(bounded(raw))
                    except (ValueError, TypeError, EpisodeIntegrityError):
                        invalid = {'not_retained':'invalid_or_oversized_json'}
                    state['history'].append({'stage':stage,'operation':operation,
                        'status':'invalid_result','result':invalid})
                state['pending'] = None
                self.store.save(state)
            self.store.save(state)
            return state
