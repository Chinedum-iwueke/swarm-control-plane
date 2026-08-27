# AGT-004 Validation

Source validation covers:

- immutable bundle/version/digest uniqueness and append-only event chaining;
- fail-closed object schemas and data-only output authority;
- model/runtime/version, trust-label, tool and data-class binding;
- deterministic rejection of missing, mistyped, undeclared, injection-shaped, secret-shaped and authority-bearing output;
- complete adversarial-category and independent-review requirements before approval or activation;
- prior-version retirement on replacement activation; and
- an idempotent no-action pilot retaining bundle, evaluation and event-chain digests.

Production completion requires migration `c4f8a2d61e90`, rebuilt VM2 API deployment and one live `worker/scripts/agt004_pilot.py` report. Until that evidence exists, AGT-004 is source-complete rather than production-complete.
