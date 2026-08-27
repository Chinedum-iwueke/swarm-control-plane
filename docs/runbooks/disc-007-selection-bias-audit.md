# DISC-007 Selection-Bias Audit Runbook

DISC-007 accepts only a finalized, digest-bound complete search-family ledger. The
ledger includes completed, failed and cancelled trials, the preregistered stopping
rule, every observed researcher operation and validation-split ranks. Winner-only
summaries are not admissible.

## Contract

1. Complete BT-006 search-plan and execution accounting.
2. Retain a DISC-006 mechanism evaluation.
3. Register the family ledger before requesting selection adjustment.
4. Correct across the complete planned family; the effective trial count cannot be
   reduced at audit time.
5. Treat optional stopping and undeclared researcher degrees as blocking findings.
6. Interpret `selection_adjusted` as eligibility for independent review, never as
   promotion or trading authority.

The audit reports Bonferroni family-wise p, Benjamini-Hochberg discoveries, a
selection-adjusted Sharpe diagnostic and validation-split probability of backtest
overfitting. Failed or cancelled trials remain visible in every replay.

## Rollback

Disable new audit registration and retain existing ledgers/audits. Corrections use a
new immutable audit with `supersedes_audit_id`; they never edit a trial, erase a failed
attempt or change a prior conclusion in place.
