"""Explicit same-task publication recovery, never a substitute reviewer call."""
import json
import re

from swarm_worker.review_context import canonical
from swarm_worker.review_evidence import verify_evidence, validate_coverage
from swarm_worker.strategy_review_contract import MethodStrategyReview, review_digest
from swarm_worker.method_verdict_contract import complete_rejection_summary, validate_method_review


def retained_review(task, workspace, contract, manifest, request):
    if (contract.subject.get('review_scope') != 'method_design'
            or manifest.get('schema_version') != 'review-context-file-v1'
            or request.get('contract_digest') != review_digest(contract.model_dump(mode='json'))
            or (task.failure or {}).get('detail') != 'Method blockers differ from retained findings'):
        raise ValueError('Review recovery requires the exact retained publication failure')
    attempt = request.get('source_attempt', '')
    match = re.fullmatch(r'attempt-(\d+)(?:-execution-[a-f0-9]{64})?', attempt)
    if not match or int(match[1]) >= task.attempt_count:
        raise ValueError('Review recovery requires an earlier same-task attempt')
    root = workspace.plan.attempt_directory.parent
    source = root / attempt
    for path in (source, source / 'artifacts', source / 'metadata.json'):
        if path.is_symlink():
            raise ValueError('Unsafe review recovery path')
    metadata_path = source / 'metadata.json'
    if metadata_path.stat().st_size > 16384:
        raise ValueError('Review recovery metadata exceeds bound')
    metadata = json.loads(metadata_path.read_text())
    if (metadata.get('task_id') != str(task.id)
            or metadata.get('attempt_number') != int(match[1])
            or metadata.get('resolved_base_commit') != contract.base_ref
            or metadata.get('repository') != contract.repository):
        raise ValueError('Review recovery workspace identity mismatch')
    verify_evidence(source / 'artifacts' / manifest['file'], manifest)
    output = source / 'artifacts' / 'strategy-review.json'
    if output.is_symlink() or not output.is_file() or output.stat().st_size > 100000:
        raise ValueError('Invalid retained review artifact')
    raw = json.loads(output.read_text())
    if review_digest(raw) != request.get('raw_review_digest'):
        raise ValueError('Retained review digest mismatch')
    coverage = raw.get('evidence_coverage')
    validate_coverage(coverage, manifest)
    review = MethodStrategyReview.model_validate({k: v for k, v in raw.items() if k != 'evidence_coverage'})
    review = complete_rejection_summary(review)
    if review.subject_digest != contract.subject_digest:
        raise ValueError('Retained review subject mismatch')
    validate_method_review(review, contract.qualification['artifact_bundle']['method_review_packet'], review_digest)
    target = workspace.artifacts / 'retained-strategy-review.json'
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.read_text() != canonical(raw):
            raise ValueError('Recovered artifact changed')
    else:
        with target.open('x') as stream:
            stream.write(canonical(raw))
        target.chmod(0o400)
    return review, coverage
