"""Bind accepted methods to approved engineering work, never execution authority."""
from copy import deepcopy

from swarm_worker.engineering_episode import canonical_digest as digest, EpisodeIntegrityError
from swarm_worker.engineering_evidence import decode_engineering_evidence, encode_engineering_evidence
from swarm_worker.method_review import MethodVerdict


KEY = 'accepted_method_handoff'


def contract_basis(contract):
    value=contract.model_dump(mode='json')
    evidence=decode_engineering_evidence(value['evidence_context'])
    evidence.pop(KEY,None)
    value['evidence_context']=encode_engineering_evidence(evidence)
    return digest(value)


def verify_handoff(contract, source):
    try:
        return _verify_handoff(contract, source)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise EpisodeIntegrityError('malformed accepted method handoff') from exc


def _verify_handoff(contract, source):
    evidence=decode_engineering_evidence(contract.evidence_context)
    h=evidence.get(KEY)
    if h is None:
        return None  # Legacy contracts retain their existing gates.
    if not isinstance(h,dict) or h.get('schema_version')!='accepted-method-engineering-handoff-v1':
        raise EpisodeIntegrityError('invalid accepted method handoff')
    if (h.get('handoff_digest')!=digest({k:v for k,v in h.items() if k!='handoff_digest'})
            or h.get('contract_basis_digest')!=contract_basis(contract)
            or source!=contract.base_ref or h['packet']['source_commit']!=source
            or contract.engineering_episode is None
            or h.get('execution_authority') is not False):
        raise EpisodeIntegrityError('accepted method source/contract binding differs')
    packet=h['packet']
    if set(h['reviews'])!={'strategy_spec','causality_leakage'}:
        raise EpisodeIntegrityError('both method reviews required')
    for record in h['reviews'].values():
        verdict=MethodVerdict.model_validate(record['verdict'])
        if (verdict.verdict!='accept' or verdict.packet_digest!=digest(packet)
                or set(verdict.checks)!=set(packet['requirements'])):
            raise EpisodeIntegrityError('method reviews do not accept exact packet')
    identities=h['review_identity_bindings']
    for kind,record in h['reviews'].items():
        if record['identity']!=identities['reviewers'][kind]:
            raise EpisodeIntegrityError('review profile differs from registered assignment')
    agents=[v['identity']['agent_id'] for v in h['reviews'].values()]
    contexts=[v['identity']['context_group'] for v in h['reviews'].values()]
    if (len(set(agents))!=2 or len(set(contexts))!=2
            or any(p['agent_id'] in agents or p['context_group'] in contexts for p in identities['producers'])):
        raise EpisodeIntegrityError('method review independence changed')
    report=packet['evidence'].get(h['plan_evidence_digest'])
    if not isinstance(report,dict) or digest(report)!=h['plan_evidence_digest']:
        raise EpisodeIntegrityError('native plans not in accepted evidence')
    plans=report.get('validation_plans',{})
    if set(plans)!={'smoke','scientific'}:
        raise EpisodeIntegrityError('separate smoke/scientific native plans required')
    for mode,plan in plans.items():
        if (plan.get('plan_digest')!=digest({k:v for k,v in plan.items() if k!='plan_digest'})
                or plan.get('source_commit')!=source or plan.get('mode')!=mode
                or plan.get('schema_version')!='requirements-aware-validation-plan-v1'
                or plan.get('status')!='ready' or plan.get('reasons')
                or not plan.get('partitions') or plan.get('execution_authority') is not False):
            raise EpisodeIntegrityError('native plan is not ready and exactly source-bound')
    return h


def bind_accepted_method(contract, review_state, *, plan_evidence_digest, registration_receipt, current):
    """Trusted materializer verifies AGT-006 custody; returned contract needs normal approval."""
    if (review_state.get('status')!='review_complete'
            or review_state.get('execution_authority') is not False
            or not isinstance(registration_receipt,dict) or not registration_receipt
            or current(deepcopy(review_state),deepcopy(registration_receipt)) is not True):
        raise EpisodeIntegrityError('registered current independent review required')
    evidence=decode_engineering_evidence(contract.evidence_context)
    if KEY in evidence:
        raise EpisodeIntegrityError('do not rebind a frozen handoff')
    h=dict(schema_version='accepted-method-engineering-handoff-v1',
        review_state_digest=digest(review_state),packet=deepcopy(review_state['packet']),
        reviews=deepcopy(review_state['reviews']),registration_receipt=deepcopy(registration_receipt),
        review_identity_bindings=deepcopy(review_state['binding']),
        plan_evidence_digest=plan_evidence_digest,contract_basis_digest=contract_basis(contract),
        execution_authority=False)
    h['handoff_digest']=digest(h)
    evidence[KEY]=h
    result=contract.model_copy(update={'evidence_context':encode_engineering_evidence(evidence)})
    verify_handoff(result,contract.base_ref)
    return result


def bundle_binding(handoff, state, *, contract, patch, bundle):
    """An immutable linkage artifact, not a native run or a promotion receipt."""
    if state['status']!='completed':
        raise EpisodeIntegrityError('engineering episode incomplete')
    code=state['code_digest']
    if code!=digest([contract.base_ref,patch]) or bundle.get('base_commit')!=contract.base_ref:
        raise EpisodeIntegrityError('bundle patch differs from reviewed code fingerprint')
    receipts={}
    for stage in ('focused','review','validation','bundle'):
        events=[(index,e) for index,e in enumerate(state['events']) if e.get('stage')==stage and e.get('code_digest')==code
                and e.get('result',{}).get('status')=='pass']
        if not events:
            raise EpisodeIntegrityError('missing same-code passing stage: '+stage)
        index,event=events[-1]
        expected=digest([state['binding'],index,stage,code,event['result']])
        if event['receipt_id']!=expected:
            raise EpisodeIntegrityError('engineering stage receipt binding differs')
        receipts[stage]=expected
    result=dict(schema_version='accepted-method-native-handoff-v1',
        source_commit=contract.base_ref,contract_digest=digest(contract.model_dump(mode='json')),
        accepted_method_digest=handoff['handoff_digest'],packet_digest=digest(handoff['packet']),
        code_digest=code,patch_digest=digest(patch),bundle_digest=digest(bundle),stage_receipts=receipts,
        validation_plan_digests={mode:plan['plan_digest'] for mode,plan in
            handoff['packet']['evidence'][handoff['plan_evidence_digest']]['validation_plans'].items()},
        execution_authority=False,scientific_certification=False)
    return result|{'receipt_digest':digest(result)}
