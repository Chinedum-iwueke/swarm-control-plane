# AGT-009 Held-Out Workflow Skill Optimization

AGT-009 turns repeated successful and failed task traces into proposed reusable skills.
The source gate follows the useful SkillOpt pattern: trace-backed bounded Markdown
changes, replay on historical tasks, a held-out no-regression gate and staged adoption.

The proposer and evaluator must be different identities. A candidate cannot expand tool
authority, include secret-like content, omit source traces, omit held-out replay or
underperform the current skill. Passing creates `staged_for_human_adoption`; it does
not edit a live role package, deploy itself or approve its own use. Negative candidates
remain evidence for later distillation.

Production closure still requires the AGT-009 registry, immutable diff and evaluation
receipts, independent routing, package signing, Mission Control review and rollback.

