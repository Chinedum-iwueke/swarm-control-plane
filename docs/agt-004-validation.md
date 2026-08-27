# AGT-004 Validation

Source validation covers:

- immutable bundle/version/digest uniqueness and append-only event chaining;
- fail-closed object schemas and data-only output authority;
- model/runtime/version, trust-label, tool and data-class binding;
- deterministic rejection of missing, mistyped, undeclared, injection-shaped, secret-shaped and authority-bearing output;
- complete adversarial-category and independent-review requirements before approval or activation;
- prior-version retirement on replacement activation; and
- an idempotent no-action pilot retaining bundle, evaluation and event-chain digests.

Production completion was observed on 2026-08-27. VM2 runs migration `c4f8a2d61e90` and healthy API image `sha256:fdff00991e70d7e7939be8cd9ea60a53b47396630c5d820d6036038af94abeda`. Live bundle `12d23600-6ee5-401b-b43e-0f016641e046` is active at digest `b00090c9cef72f22eeb56b096854f48bfe81ffefcd4f7b48b2a6ff9a28cf81e3`. All five required valid/adversarial categories passed, the nine-event chain was retained, and `action_authority` remained false. The retained report is `docs/evidence/agt004-report.json` with digest `8fc5f2047ebce3be5d9f204e05eef1aadebc029d1c3e4bafc99f0cba9aa99c99`.
