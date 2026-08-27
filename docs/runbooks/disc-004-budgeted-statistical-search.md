# DISC-004 Budgeted Statistical Search

DISC-004 proposes bounded trial specifications from one immutable DISC-003 program. It never executes trials, edits results, stops on favorable outcomes, selects production candidates, or holds capital authority.

## Contract

- Methods are exhaustive, structured, seeded random, Bayesian surrogate ranking, and evolutionary neighborhood ranking.
- A campaign binds the factor-program digest, objective/direction, seed, exploration weight, maximum evaluations, batches, and batch size.
- Each proposal is selected from the registered finite trial universe and binds the complete prior event-history digest.
- Every proposal in a batch must receive an immutable completed, failed, cancelled, or invalid observation before another batch.
- Every observation consumes evaluation budget. Non-results cannot carry objective values.
- Completion occurs only when the fixed evaluation budget has been observed. Operator cancellation is terminal and labels all remaining trials as non-results.
- An append-only digest chain retains registration, every proposal, every observation, completion, and cancellation.

## Rollback

Disable new campaign creation and cancel active campaigns with a retained reason. Never delete proposed trials or observations. Consumers pin the last accepted specification and event-head digests.
