from swarm_worker.skill_improvement import (
    SkillImprovementCandidate,
    qualify_skill_improvement,
)


def candidate(**changes):
    values = {
        "candidate_id": "skill-1",
        "base_digest": "a" * 64,
        "proposed_markdown": "Use the typed parser and retain negative results.",
        "source_trace_digests": ("b" * 64,),
        "held_out_replay_digests": ("c" * 64,),
        "proposer_identity": "workflow-distiller",
        "evaluator_identity": "independent-skill-evaluator",
        "authority_before": ("research:read",),
        "authority_after": ("research:read",),
        "baseline_pass_rate": 0.8,
        "candidate_pass_rate": 0.9,
        "regression_count": 0,
    }
    values.update(changes)
    return SkillImprovementCandidate(**values)


def test_qualified_skill_is_staged_not_automatically_adopted() -> None:
    decision = qualify_skill_improvement(candidate())

    assert decision.qualified
    assert decision.stage == "staged_for_human_adoption"


def test_skill_diff_rejects_self_evaluation_authority_and_regression() -> None:
    decision = qualify_skill_improvement(
        candidate(
            evaluator_identity="workflow-distiller",
            authority_after=("research:read", "shell:write"),
            candidate_pass_rate=0.7,
            regression_count=1,
        )
    )

    assert not decision.qualified
    assert set(decision.reasons) == {
        "independent_evaluator_required",
        "tool_authority_expansion_forbidden",
        "held_out_regression_detected",
        "candidate_underperforms_baseline",
    }


def test_skill_diff_rejects_secret_like_content() -> None:
    decision = qualify_skill_improvement(
        candidate(proposed_markdown="API_KEY=do-not-store-this")
    )

    assert decision.reasons == ("secret_like_content_detected",)
