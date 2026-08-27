# AGT-004 Prompt, Policy and Model-Output Security Registry

AGT-004 treats prompts, policies and model outputs as versioned governed inputs, never executable authority. Each immutable bundle binds its exact model provider, model, runtime and version; prompt template; instruction precedence; trust labels; tool/data allowlists; fail-closed input/output schemas; and secret, injection and authority policy.

## Lifecycle

1. Register a unique semantic version and canonical bundle digest in `draft`.
2. Record valid-output and adversarial fixtures as immutable evaluation receipts.
3. Promote through `draft -> rehearsed -> approved -> active` only after all required categories pass and an evaluator independent of the producer participates.
4. Activating a replacement retires the prior active version while preserving its full event chain.
5. Consumers may use only the active digest and must still pass workload authorization and task-specific approval. An accepted output is data, not permission to execute.

Required adversarial categories are prompt injection, secret exfiltration, malformed output and instruction collision. The deterministic gate rejects schema violations, undeclared fields, forbidden authority fields and configured secret/injection patterns before output may enter another governed service.

## Boundaries

- Prompt text cannot expand a task, grant, tool, machine, secret or capital boundary.
- Untrusted corpus and external text remain explicitly labelled and subordinate to system/operator policy.
- Secrets must never enter prompts, fixtures, outputs, receipts, events or Mission Control.
- Evaluation evidence proves behavior only for the exact bundle/model/runtime digest; changing any component creates a new version.
- Rollback retires the new bundle and reactivates a previously qualified digest through a new governed event. History is never rewritten.
