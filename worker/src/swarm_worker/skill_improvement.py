from __future__ import annotations

import re
from dataclasses import dataclass

_SECRET = re.compile(
    r"(?i)(api[_-]?key|authorization:\s*bearer|password\s*=|private[_-]?key)"
)


@dataclass(frozen=True)
class SkillImprovementCandidate:
    candidate_id: str
    base_digest: str
    proposed_markdown: str
    source_trace_digests: tuple[str, ...]
    held_out_replay_digests: tuple[str, ...]
    proposer_identity: str
    evaluator_identity: str
    authority_before: tuple[str, ...]
    authority_after: tuple[str, ...]
    baseline_pass_rate: float
    candidate_pass_rate: float
    regression_count: int


@dataclass(frozen=True)
class SkillImprovementDecision:
    qualified: bool
    stage: str
    reasons: tuple[str, ...]


def qualify_skill_improvement(
    candidate: SkillImprovementCandidate,
) -> SkillImprovementDecision:
    """Gate a SkillOpt-style skill diff; never adopts it into production."""
    reasons: list[str] = []
    if not candidate.source_trace_digests:
        reasons.append("source_traces_required")
    if not candidate.held_out_replay_digests:
        reasons.append("held_out_replay_required")
    if candidate.proposer_identity == candidate.evaluator_identity:
        reasons.append("independent_evaluator_required")
    if set(candidate.authority_after) - set(candidate.authority_before):
        reasons.append("tool_authority_expansion_forbidden")
    if candidate.regression_count:
        reasons.append("held_out_regression_detected")
    if candidate.candidate_pass_rate < candidate.baseline_pass_rate:
        reasons.append("candidate_underperforms_baseline")
    if _SECRET.search(candidate.proposed_markdown):
        reasons.append("secret_like_content_detected")
    if reasons:
        return SkillImprovementDecision(False, "rejected", tuple(reasons))
    return SkillImprovementDecision(True, "staged_for_human_adoption", ())
