# Scientific correction stage ownership

## Failure observed

R2 hypothesis task 061f3a97-2e36-4959-ab9f-320f4a8d8252 abstained because its
instructions demanded complete corrected methods while its schema accepted only
a hypothesis card. The representation stage owns the method fields. Inspection
also found that representation prompt compaction discarded founder_research_idea,
including retained recovery identity, rejected methods and the correction worklist.
Its schema still saw the original context, so schema and prompt disagreed.

## Repair

Stage-specific instructions now keep responsibilities aligned with existing schemas:

- Intelligence synthesizes evidence and unresolved blockers.
- Hypothesis emits the retained, schema-valid question card, without serializing
  corrected method documents into unrelated prose fields.
- Representation receives the full recovery scope and worklist. It emits corrected
  methods with the frozen support keys/minima, affected fields and verification
  stages. Algorithm definitions and prospective feasibility are distinguished
  from checks whose observed results require construction/execution.

The representation context allowlist preserves founder_research_idea losslessly.
No new authority, schema relaxation, inferred approval or scientific claim follows
from this repair. Substantive infeasibility still permits abstention.

## Evidence

Forty worker tests pass, including stage/schema alignment and single-/multi-asset
recovery-context preservation. A read-only replay of the real R2 input retained all
nine blocker records and exact registered support minima through both stages.
Worklist digest: 5e2260487134e166849c055e28e5aa98aef4f5fb45cd7953e723f94628e7696d.

No model inference was used in that replay; it does not prove a scientifically
acceptable correction. The completed R2 cycle remains immutable and spent.
Continuation requires a newly approved exact-digest mandate, not resetting R2.
