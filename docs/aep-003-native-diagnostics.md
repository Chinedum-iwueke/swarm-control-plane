# AEP-003: native diagnostic receipt custody

Implemented on 2026-11-17. Not deployed or scientifically commissioned by this
change. Quantitative computation belongs to Bulletproof, not the control plane.

Bulletproof's `docs/aep-003-native-diagnostics.md` defines the tool registry,
design-adequacy contract, bounded seeded calibration and clean-source CLI. The
registered residual diagnostic is explicitly a frozen-residual approximation to
full strategy inference; it cannot certify fitted OLS, paired power or joint Holm.
Unsupported requests return `await_engineering`, never a substituted estimator.

## Handoff

1. An authorized producer includes an optional `diagnostic_request` and
   content-addressed `diagnostic_evidence_catalog` in native feasibility evidence.
2. Bulletproof checks candidate/source identity, argument and work bounds, and
   emits `native-diagnostic-receipt-v1` inside the feasibility report.
3. `alpha_requirements_feasibility.verified_report` calls
   `native_diagnostics.verify_diagnostic`. It checks request, evidence, candidate,
   source and receipt digests, implementation hashes and false authority flags.
4. An unavailable tool forces deferral. `alpha_disposition.disposition_for` maps
   that reason to `await_authority_or_capacity`; engineering approval is required.

No diagnostic is silently inserted into existing tasks. An unsolicited or missing
receipt, changed binding or nested approval claim fails closed. Content hashes
prove content integrity, not authenticity or scientific truth; authenticated task
custody and independent review remain required. Legacy tasks without requests
retain their previous behavior.

## Boundaries and rollback

Model-driven tool selection and bounded method correction are AEP-004 integration
work. Creating an engineering task for a missing tool is not implemented here.
Callers can disable individual native tool versions; omit optional diagnostics to
retain the existing feasibility path for new inputs. Do not rewrite frozen tasks.
Source transition, live handoff validation, independent quantitative review and
end-to-end acceptance remain separate from these implementation tests.

Regression coverage includes binding/tamper failures, authority escalation,
missing/unrequested diagnostics, readiness contradictions and typed deferral.

## Verification record

On 2026-11-17, 360 focused control-plane tests and 137 native tests passed.
The clean-source CLI at Bulletproof `4e98fab3c1073d8a5c83615ecbe2c0a428193b7c`
ran all three registered DGPs with 100 outer experiments, 199 inner draws,
80 rows, block length 12 and effect .25 residual SD. Two runs produced identical
receipt `b21abfc1d67aeb0b7d5eeadb54a70a840dc983b80fb345b43f7aabd65b059e72`;
the actual backend verifier accepted its custody bindings. Work count: 705900.

Invalid experiment counts were 36, 38 and 37 out of 100 respectively. Coverage
conditional on valid experiments was 57/64, 57/62 and 50/63. These are diagnostic
warnings, not satisfactory calibration or candidate acceptance. The pilot proves
reproducible execution, explicit invalid denominators and cross-repository receipt
compatibility only. No raw market output was created or committed.
